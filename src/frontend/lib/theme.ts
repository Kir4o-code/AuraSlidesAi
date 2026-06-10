import type { CSSProperties } from "react";

import type { ThemeName } from "@/lib/api";

type ThemeRegistryKey = Exclude<ThemeName, "modern_dark" | "modern_light" | "editorial" | "corporate" | "playful">;

export interface ThemeTokens {
  name: ThemeName;
  displayName: string;
  description: string;
  useCases: string[];
  tags: string[];
  palette: string[];
  background: string;
  backgroundAlt: string;
  surface: string;
  textColor: string;
  mutedTextColor: string;
  accentColor: string;
  accentSoftColor: string;
  borderColor: string;
  fontFamily: string;
  headingFontFamily: string;
  bodyFontFamily: string;
  borderRadius: string;
  shadow: string;
  spacingScale: number;
  typographyScale: number;
  imageStyle: string;
  layoutStyle: string;
  panelStyle: "rounded" | "square";
  bulletStyle: "cards" | "lines";
  accentPosition: "left" | "top";
  panelRadius: number;
  panelPadding: number;
  imageRadius: number;
  imageFrameInset: number;
  imageFit: "cover" | "contain";
}

const defaults: Pick<
  ThemeTokens,
  | "panelStyle"
  | "bulletStyle"
  | "accentPosition"
  | "panelRadius"
  | "panelPadding"
  | "imageRadius"
  | "imageFrameInset"
  | "imageFit"
> = {
  panelStyle: "rounded",
  bulletStyle: "cards",
  accentPosition: "left",
  panelRadius: 24,
  panelPadding: 24,
  imageRadius: 22,
  imageFrameInset: 6,
  imageFit: "cover",
};

function defineTheme(
  tokens: Omit<
    ThemeTokens,
    | "panelStyle"
    | "bulletStyle"
    | "accentPosition"
    | "panelRadius"
    | "panelPadding"
    | "imageRadius"
    | "imageFrameInset"
    | "imageFit"
  > &
    Partial<typeof defaults>,
): ThemeTokens {
  return { ...defaults, ...tokens };
}

export const THEME_REGISTRY: Record<ThemeRegistryKey, ThemeTokens> = {
  clean_school: defineTheme({
    name: "clean_school",
    displayName: "Clean School",
    description: "Bright, friendly structure with calm educational accents.",
    useCases: ["school projects", "classroom explainers", "general learning"],
    tags: ["bright", "readable", "friendly"],
    palette: ["#F8FBFF", "#FFFFFF", "#2563EB", "#BFDBFE"],
    background: "#F8FBFF",
    backgroundAlt: "#EAF3FF",
    surface: "#FFFFFF",
    textColor: "#172033",
    mutedTextColor: "#526176",
    accentColor: "#2563EB",
    accentSoftColor: "#BFDBFE",
    borderColor: "#C9DCF5",
    fontFamily: "'Inter', 'Aptos', sans-serif",
    headingFontFamily: "'Nunito', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Inter', 'Aptos', sans-serif",
    borderRadius: "26px",
    shadow: "0 18px 48px rgba(37, 99, 235, 0.12)",
    spacingScale: 1.08,
    typographyScale: 1,
    imageStyle: "soft_frame",
    layoutStyle: "airy",
    panelPadding: 28,
    imageFrameInset: 8,
  }),
  modern_dark_tech: defineTheme({
    name: "modern_dark_tech",
    displayName: "Modern Dark Tech",
    description: "High-contrast panels and cool accents for technical ideas.",
    useCases: ["AI", "apps", "hackathons", "software"],
    tags: ["dark", "technical", "high contrast"],
    palette: ["#07111F", "#10243E", "#67E8F9", "#8B5CF6"],
    background: "#07111F",
    backgroundAlt: "#10243E",
    surface: "#132A46",
    textColor: "#F8FAFC",
    mutedTextColor: "#B8C8DB",
    accentColor: "#67E8F9",
    accentSoftColor: "#8B5CF6",
    borderColor: "#31506F",
    fontFamily: "'Inter', 'Aptos', sans-serif",
    headingFontFamily: "'Space Grotesk', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Inter', 'Aptos', sans-serif",
    borderRadius: "22px",
    shadow: "0 24px 64px rgba(2, 8, 23, 0.42)",
    spacingScale: 1.02,
    typographyScale: 1,
    imageStyle: "dark_panel",
    layoutStyle: "panel_grid",
    panelRadius: 18,
    imageRadius: 16,
    imageFrameInset: 8,
  }),
  academic_formal: defineTheme({
    name: "academic_formal",
    displayName: "Academic Formal",
    description: "Restrained scholarly styling with comfortable reading rhythm.",
    useCases: ["research", "history", "literature", "formal reports"],
    tags: ["formal", "serif", "structured"],
    palette: ["#F7F4ED", "#FFFCF7", "#243B53", "#B08D57"],
    background: "#F7F4ED",
    backgroundAlt: "#ECE5D8",
    surface: "#FFFCF7",
    textColor: "#24313F",
    mutedTextColor: "#617080",
    accentColor: "#8A653A",
    accentSoftColor: "#D8C3A5",
    borderColor: "#D7CDBE",
    fontFamily: "'Source Sans 3', 'Aptos', sans-serif",
    headingFontFamily: "'Merriweather', 'Georgia', serif",
    bodyFontFamily: "'Source Sans 3', 'Aptos', sans-serif",
    borderRadius: "10px",
    shadow: "0 14px 30px rgba(65, 48, 32, 0.08)",
    spacingScale: 1.12,
    typographyScale: 0.96,
    imageStyle: "caption_frame",
    layoutStyle: "editorial",
    panelStyle: "square",
    bulletStyle: "lines",
    panelRadius: 8,
    panelPadding: 30,
    imageRadius: 4,
    imageFrameInset: 10,
  }),
  startup_pitch: defineTheme({
    name: "startup_pitch",
    displayName: "Startup Pitch",
    description: "Bold statements, crisp cards, and confident product energy.",
    useCases: ["product ideas", "pitch decks", "startups", "hackathons"],
    tags: ["bold", "card based", "confident"],
    palette: ["#F7F8FF", "#FFFFFF", "#5B21B6", "#F97316"],
    background: "#F7F8FF",
    backgroundAlt: "#ECE9FF",
    surface: "#FFFFFF",
    textColor: "#19152D",
    mutedTextColor: "#625C75",
    accentColor: "#5B21B6",
    accentSoftColor: "#F97316",
    borderColor: "#D9D2F3",
    fontFamily: "'Inter', 'Aptos', sans-serif",
    headingFontFamily: "'Sora', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Inter', 'Aptos', sans-serif",
    borderRadius: "22px",
    shadow: "0 20px 54px rgba(91, 33, 182, 0.16)",
    spacingScale: 1,
    typographyScale: 1.04,
    imageStyle: "accent_frame",
    layoutStyle: "statement",
    accentPosition: "top",
    panelRadius: 18,
    imageRadius: 18,
  }),
  photo_editorial: defineTheme({
    name: "photo_editorial",
    displayName: "Photo Editorial",
    description: "Image-led storytelling with cinematic neutral typography.",
    useCases: ["travel", "culture", "geography", "history"],
    tags: ["cinematic", "image first", "editorial"],
    palette: ["#171717", "#34312D", "#F8F1E7", "#D59B62"],
    background: "#171717",
    backgroundAlt: "#34312D",
    surface: "#2A2825",
    textColor: "#FFF9F0",
    mutedTextColor: "#D8CFC3",
    accentColor: "#D59B62",
    accentSoftColor: "#F0D4B7",
    borderColor: "#5B5148",
    fontFamily: "'Inter', 'Aptos', sans-serif",
    headingFontFamily: "'DM Serif Display', 'Georgia', serif",
    bodyFontFamily: "'Inter', 'Aptos', sans-serif",
    borderRadius: "12px",
    shadow: "0 24px 70px rgba(0, 0, 0, 0.32)",
    spacingScale: 1.06,
    typographyScale: 1.02,
    imageStyle: "cinematic",
    layoutStyle: "image_led",
    panelStyle: "square",
    bulletStyle: "lines",
    panelRadius: 8,
    imageRadius: 2,
    imageFrameInset: 4,
  }),
  minimal_corporate: defineTheme({
    name: "minimal_corporate",
    displayName: "Minimal Corporate",
    description: "Quiet neutral space with understated professional structure.",
    useCases: ["business", "reports", "strategy", "operations"],
    tags: ["neutral", "spacious", "professional"],
    palette: ["#F4F1EB", "#FFFEFC", "#1F2937", "#9B7B5A"],
    background: "#F4F1EB",
    backgroundAlt: "#E8E1D7",
    surface: "#FFFEFC",
    textColor: "#1F2937",
    mutedTextColor: "#667085",
    accentColor: "#826445",
    accentSoftColor: "#D9C9B7",
    borderColor: "#D7D0C6",
    fontFamily: "'Inter', 'Helvetica', sans-serif",
    headingFontFamily: "'Manrope', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Inter', 'Helvetica', sans-serif",
    borderRadius: "14px",
    shadow: "0 12px 34px rgba(31, 41, 55, 0.08)",
    spacingScale: 1.14,
    typographyScale: 0.98,
    imageStyle: "subtle_frame",
    layoutStyle: "minimal",
    panelStyle: "square",
    bulletStyle: "lines",
    panelRadius: 10,
    panelPadding: 30,
    imageRadius: 8,
  }),
  creative_gradient: defineTheme({
    name: "creative_gradient",
    displayName: "Creative Gradient",
    description: "Expressive color transitions anchored by clean components.",
    useCases: ["innovation", "creative projects", "youth topics"],
    tags: ["colorful", "gradient", "modern"],
    palette: ["#1E1B4B", "#312E81", "#A78BFA", "#22D3EE"],
    background: "#1E1B4B",
    backgroundAlt: "#312E81",
    surface: "#37308A",
    textColor: "#FFFFFF",
    mutedTextColor: "#DDD6FE",
    accentColor: "#22D3EE",
    accentSoftColor: "#A78BFA",
    borderColor: "#665FB8",
    fontFamily: "'Plus Jakarta Sans', 'Aptos', sans-serif",
    headingFontFamily: "'Outfit', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Plus Jakarta Sans', 'Aptos', sans-serif",
    borderRadius: "28px",
    shadow: "0 24px 68px rgba(15, 10, 65, 0.38)",
    spacingScale: 1.04,
    typographyScale: 1.02,
    imageStyle: "gradient_frame",
    layoutStyle: "expressive",
    accentPosition: "top",
    panelRadius: 24,
  }),
  data_report: defineTheme({
    name: "data_report",
    displayName: "Data Report",
    description: "Analytical grid system optimized for evidence and metrics.",
    useCases: ["statistics", "science", "comparisons", "analytics"],
    tags: ["analytical", "dashboard", "grid"],
    palette: ["#F5F8FA", "#FFFFFF", "#0F766E", "#99F6E4"],
    background: "#F5F8FA",
    backgroundAlt: "#E6F2F1",
    surface: "#FFFFFF",
    textColor: "#16323A",
    mutedTextColor: "#57717A",
    accentColor: "#0F766E",
    accentSoftColor: "#99F6E4",
    borderColor: "#C9DDDF",
    fontFamily: "'IBM Plex Sans', 'Aptos', sans-serif",
    headingFontFamily: "'IBM Plex Sans', 'Aptos Display', sans-serif",
    bodyFontFamily: "'IBM Plex Sans', 'Aptos', sans-serif",
    borderRadius: "14px",
    shadow: "0 14px 34px rgba(15, 118, 110, 0.10)",
    spacingScale: 0.98,
    typographyScale: 0.96,
    imageStyle: "evidence_frame",
    layoutStyle: "dashboard",
    panelRadius: 10,
    imageRadius: 8,
    imageFrameInset: 8,
  }),
  nature_organic: defineTheme({
    name: "nature_organic",
    displayName: "Nature Organic",
    description: "Earth-toned cards and calm visual pacing for natural topics.",
    useCases: ["ecology", "biology", "agriculture", "geography"],
    tags: ["earth tones", "soft", "organic"],
    palette: ["#F5F4EA", "#FFFEF7", "#4D7C5B", "#C8D5B9"],
    background: "#F5F4EA",
    backgroundAlt: "#E6E8D4",
    surface: "#FFFEF7",
    textColor: "#26362B",
    mutedTextColor: "#657566",
    accentColor: "#4D7C5B",
    accentSoftColor: "#C8D5B9",
    borderColor: "#D2D8C5",
    fontFamily: "'Nunito', 'Aptos', sans-serif",
    headingFontFamily: "'Fraunces', 'Georgia', serif",
    bodyFontFamily: "'Nunito', 'Aptos', sans-serif",
    borderRadius: "28px",
    shadow: "0 18px 44px rgba(77, 124, 91, 0.12)",
    spacingScale: 1.1,
    typographyScale: 1,
    imageStyle: "organic_frame",
    layoutStyle: "organic",
    panelRadius: 28,
    panelPadding: 28,
    imageRadius: 28,
    imageFrameInset: 8,
  }),
  luxury_editorial: defineTheme({
    name: "luxury_editorial",
    displayName: "Luxury Editorial",
    description: "Premium serif hierarchy with high whitespace and restraint.",
    useCases: ["art", "fashion", "architecture", "culture"],
    tags: ["premium", "serif", "whitespace"],
    palette: ["#FAF7F2", "#FFFFFF", "#1C1B1A", "#A98352"],
    background: "#FAF7F2",
    backgroundAlt: "#EEE7DE",
    surface: "#FFFFFF",
    textColor: "#1C1B1A",
    mutedTextColor: "#746B62",
    accentColor: "#A98352",
    accentSoftColor: "#E2D0B6",
    borderColor: "#DED5CA",
    fontFamily: "'Inter', 'Helvetica', sans-serif",
    headingFontFamily: "'Cormorant Garamond', 'Georgia', serif",
    bodyFontFamily: "'Inter', 'Helvetica', sans-serif",
    borderRadius: "6px",
    shadow: "0 12px 30px rgba(40, 31, 24, 0.08)",
    spacingScale: 1.18,
    typographyScale: 1.04,
    imageStyle: "gallery_frame",
    layoutStyle: "luxury",
    panelStyle: "square",
    bulletStyle: "lines",
    panelRadius: 4,
    panelPadding: 32,
    imageRadius: 2,
    imageFrameInset: 10,
  }),
  playful_learning: defineTheme({
    name: "playful_learning",
    displayName: "Playful Learning",
    description: "Colorful rounded cards that stay classroom-safe and clear.",
    useCases: ["younger learners", "classroom activities", "explainers"],
    tags: ["colorful", "rounded", "friendly"],
    palette: ["#FFF8EE", "#FFFFFF", "#EA580C", "#FDE68A"],
    background: "#FFF8EE",
    backgroundAlt: "#FEF3C7",
    surface: "#FFFFFF",
    textColor: "#3F2B20",
    mutedTextColor: "#7C6254",
    accentColor: "#EA580C",
    accentSoftColor: "#FDE68A",
    borderColor: "#F2D6B6",
    fontFamily: "'Nunito', 'Aptos', sans-serif",
    headingFontFamily: "'Nunito', 'Aptos Display', sans-serif",
    bodyFontFamily: "'Nunito', 'Aptos', sans-serif",
    borderRadius: "30px",
    shadow: "0 18px 44px rgba(234, 88, 12, 0.12)",
    spacingScale: 1.04,
    typographyScale: 1,
    imageStyle: "soft_frame",
    layoutStyle: "friendly",
    panelRadius: 28,
    panelPadding: 26,
    imageRadius: 26,
  }),
  monochrome_bold: defineTheme({
    name: "monochrome_bold",
    displayName: "Monochrome Bold",
    description: "Graphic black-and-white hierarchy with one decisive accent.",
    useCases: ["editorial", "keynotes", "brand concepts", "portfolios"],
    tags: ["monochrome", "graphic", "export safe"],
    palette: ["#F7F7F5", "#FFFFFF", "#111111", "#E11D48"],
    background: "#F7F7F5",
    backgroundAlt: "#E8E8E4",
    surface: "#FFFFFF",
    textColor: "#111111",
    mutedTextColor: "#595959",
    accentColor: "#E11D48",
    accentSoftColor: "#FECDD3",
    borderColor: "#CFCFCA",
    fontFamily: "'Inter', 'Helvetica', sans-serif",
    headingFontFamily: "'Archivo', 'Arial', sans-serif",
    bodyFontFamily: "'Inter', 'Helvetica', sans-serif",
    borderRadius: "4px",
    shadow: "0 12px 28px rgba(17, 17, 17, 0.10)",
    spacingScale: 1.02,
    typographyScale: 1.06,
    imageStyle: "graphic_frame",
    layoutStyle: "graphic",
    panelStyle: "square",
    bulletStyle: "lines",
    accentPosition: "top",
    panelRadius: 2,
    imageRadius: 0,
  }),
};

const THEME_ALIASES: Record<string, ThemeName> = {
  modern: "modern_dark_tech",
  modern_dark: "modern_dark_tech",
  minimal: "clean_school",
  modern_light: "clean_school",
  editorial: "photo_editorial",
  corporate: "minimal_corporate",
  playful: "playful_learning",
};

export const TEMPLATE_OPTIONS = Object.values(THEME_REGISTRY);

export function resolveThemeTokens(themeName: ThemeName | string | null | undefined): ThemeTokens {
  const resolved = themeName ? THEME_ALIASES[themeName] ?? themeName : "modern_dark_tech";
  return THEME_REGISTRY[resolved as ThemeRegistryKey] ?? THEME_REGISTRY.modern_dark_tech;
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
    "--presentation-heading-font": tokens.headingFontFamily,
    "--presentation-body-font": tokens.bodyFontFamily,
    "--presentation-spacing": `${tokens.spacingScale}`,
    "--presentation-type-scale": `${tokens.typographyScale}`,
  } as CSSProperties;
}
