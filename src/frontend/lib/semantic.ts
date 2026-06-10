export type RendererTarget = "react" | "pptx" | "pdf" | "screenshot" | "editor";

export type SemanticAlignment = "start" | "center" | "end";
export type LayoutRegionRole = "title" | "body" | "media" | "footer" | "aside";
export type MediaKind = "image" | "chart" | "icon" | "illustration" | "video" | "audio" | "other";

export interface ThemeFonts {
  heading: string;
  body: string;
  mono?: string | null;
  fallbacks: string[];
}

export interface ThemeTokens {
  background: string;
  backgroundAlt: string;
  surface: string;
  surfaceAlt?: string | null;
  textPrimary: string;
  textSecondary: string;
  accentPrimary: string;
  accentSecondary: string;
  border: string;
  focusRing?: string | null;
  fonts: ThemeFonts;
  spacingScale: number;
  typographyScale: number;
  radiusScale: number;
  shadowScale: number;
  componentStyles: Record<string, Record<string, string | number | boolean | null>>;
}

export interface ThemeDefinition {
  id: string;
  name: string;
  description?: string | null;
  version: string;
  tokens: ThemeTokens;
  tags: string[];
}

export interface SlideMediaRef {
  kind: MediaKind;
  label?: string | null;
  prompt?: string | null;
  alt?: string | null;
  source?: string | null;
  sourceUrl?: string | null;
  localPath?: string | null;
  publicUrl?: string | null;
  metadata: Record<string, unknown>;
}

export interface SemanticSlide {
  id: string;
  order: number;
  layoutName: string;
  title?: string | null;
  subtitle?: string | null;
  bullets: string[];
  imagePrompt?: string | null;
  notes?: string | null;
  leftTitle?: string | null;
  rightTitle?: string | null;
  leftBullets: string[];
  rightBullets: string[];
  timeline: Array<Record<string, unknown>>;
  statistics: Array<Record<string, unknown>>;
  quote?: string | null;
  attribution?: string | null;
  media: SlideMediaRef[];
}

export interface PresentationDocument {
  title: string;
  version: string;
  metadata: Record<string, unknown>;
  slides: SemanticSlide[];
}

export interface LayoutRegion {
  id: string;
  role: LayoutRegionRole;
  alignment: SemanticAlignment;
  emphasis: "primary" | "secondary" | "supporting";
  weight: number;
  contentHints: string[];
  repeatable: boolean;
}

export interface LayoutSpec {
  name: string;
  description?: string | null;
  regions: LayoutRegion[];
  alignment: "left" | "center" | "right" | "split" | "grid";
  emphasis: "single" | "primary-secondary" | "balanced";
  columns: number;
  supportsMedia: boolean;
  supportsNotes: boolean;
  supportsFooter: boolean;
}

export interface RendererCapabilities {
  supportsCss: boolean;
  supportsWebFonts: boolean;
  supportsBlur: boolean;
  supportsAnimations: boolean;
  supportsGradients: boolean;
  supportsShadows: boolean;
  supportsAbsolutePositioning: boolean;
  supportsEditableText: boolean;
  supportsVectorOutput: boolean;
  supportsResponsiveLayout: boolean;
}

export interface RendererContext {
  target: RendererTarget;
  capabilities: RendererCapabilities;
  constraints: {
    fontFallbacks: string[];
    maxTextColumns: number;
    maxImageCount: number;
    allowExternalAssets: boolean;
    allowBlurEffects: boolean;
    allowAnimations: boolean;
  };
}

export const RENDERER_CAPABILITY_MATRIX: Record<RendererTarget, RendererCapabilities> = {
  react: {
    supportsCss: true,
    supportsWebFonts: true,
    supportsBlur: true,
    supportsAnimations: true,
    supportsGradients: true,
    supportsShadows: true,
    supportsAbsolutePositioning: true,
    supportsEditableText: true,
    supportsVectorOutput: false,
    supportsResponsiveLayout: true,
  },
  pptx: {
    supportsCss: false,
    supportsWebFonts: false,
    supportsBlur: false,
    supportsAnimations: false,
    supportsGradients: true,
    supportsShadows: false,
    supportsAbsolutePositioning: true,
    supportsEditableText: true,
    supportsVectorOutput: true,
    supportsResponsiveLayout: false,
  },
  pdf: {
    supportsCss: false,
    supportsWebFonts: true,
    supportsBlur: false,
    supportsAnimations: false,
    supportsGradients: true,
    supportsShadows: true,
    supportsAbsolutePositioning: true,
    supportsEditableText: false,
    supportsVectorOutput: false,
    supportsResponsiveLayout: false,
  },
  screenshot: {
    supportsCss: true,
    supportsWebFonts: true,
    supportsBlur: true,
    supportsAnimations: false,
    supportsGradients: true,
    supportsShadows: true,
    supportsAbsolutePositioning: true,
    supportsEditableText: false,
    supportsVectorOutput: false,
    supportsResponsiveLayout: true,
  },
  editor: {
    supportsCss: true,
    supportsWebFonts: true,
    supportsBlur: true,
    supportsAnimations: true,
    supportsGradients: true,
    supportsShadows: true,
    supportsAbsolutePositioning: true,
    supportsEditableText: true,
    supportsVectorOutput: false,
    supportsResponsiveLayout: true,
  },
};

export function assertPresentationDocument(document: PresentationDocument): PresentationDocument {
  const orders = document.slides.map((slide) => slide.order);
  const sortedOrders = [...orders].sort((left, right) => left - right);

  if (orders.length !== sortedOrders.length || orders.some((value, index) => value !== sortedOrders[index])) {
    throw new Error("PresentationDocument slides must be ordered.");
  }

  const uniqueOrders = new Set(orders);
  if (uniqueOrders.size !== orders.length) {
    throw new Error("PresentationDocument slide order must be unique.");
  }

  return document;
}

export function assertThemeDefinition(theme: ThemeDefinition): ThemeDefinition {
  if (!theme.tokens.fonts.heading || !theme.tokens.fonts.body) {
    throw new Error("ThemeDefinition requires heading and body fonts.");
  }
  return theme;
}

export function assertLayoutSpec(layout: LayoutSpec): LayoutSpec {
  const regionIds = layout.regions.map((region) => region.id);
  if (new Set(regionIds).size !== regionIds.length) {
    throw new Error(`LayoutSpec '${layout.name}' contains duplicate region ids.`);
  }
  return layout;
}

export function buildRendererContext(target: RendererTarget): RendererContext {
  return {
    target,
    capabilities: RENDERER_CAPABILITY_MATRIX[target],
    constraints: {
      fontFallbacks: ["system-ui", "sans-serif"],
      maxTextColumns: 3,
      maxImageCount: 3,
      allowExternalAssets: false,
      allowBlurEffects: target === "react" || target === "screenshot" || target === "editor",
      allowAnimations: target === "react" || target === "editor",
    },
  };
}
