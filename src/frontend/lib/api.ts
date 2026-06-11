export type ThemeName =
  | "clean_school"
  | "modern_dark_tech"
  | "academic_formal"
  | "startup_pitch"
  | "photo_editorial"
  | "minimal_corporate"
  | "creative_gradient"
  | "data_report"
  | "nature_organic"
  | "luxury_editorial"
  | "playful_learning"
  | "monochrome_bold"
  | "modern_dark"
  | "modern_light"
  | "editorial"
  | "corporate"
  | "playful";

export type SlideType =
  | "title_slide"
  | "title_bullets"
  | "title_bullets_image"
  | "hero_image"
  | "comparison"
  | "timeline"
  | "statistics"
  | "quote";

export type PlanningMode = "automatic" | "guided";

export interface GuidedSlideIntent {
  purpose: string;
  requested_type: SlideType | null;
}

export interface ResolvedImageAsset {
  local_path: string;
  public_url: string;
  source: string;
  source_url: string;
  image_url: string;
  author: string | null;
  license_name: string;
  width?: number | null;
  height?: number | null;
  clip_score?: number | null;
  final_score?: number | null;
}

export interface TimelineStep {
  label: string;
  detail?: string | null;
}

export interface StatisticItem {
  label: string;
  value: string;
  detail?: string | null;
}

export type LayoutElementKind =
  | "text"
  | "image"
  | "panel"
  | "bullet_list"
  | "bullet_item"
  | "card"
  | "timeline_step"
  | "statistic"
  | "quote";

export type LayoutAlignment = "start" | "center" | "end";

export interface LayoutDebugInfo {
  content_length: number;
  estimated_lines: number;
  estimated_chars_per_line: number;
  spacing_before: number;
  spacing_after: number;
  note?: string | null;
}

export interface LayoutElement {
  id: string;
  kind: LayoutElementKind;
  region: string;
  x: number;
  y: number;
  width: number;
  height: number;
  align: LayoutAlignment;
  wrap: boolean;
  font_size?: number | null;
  line_height?: number | null;
  z_index: number;
  text?: string | null;
  content: Record<string, unknown>;
  children: LayoutElement[];
  debug?: LayoutDebugInfo | null;
}

export interface LayoutedSlide {
  slide_id: string;
  layout_name: string;
  canvas_width: number;
  canvas_height: number;
  elements: LayoutElement[];
  debug_mode: boolean;
  debug: Record<string, unknown>;
}

export interface LayoutedPresentationDocument {
  title: string;
  version: string;
  metadata: Record<string, unknown>;
  slides: LayoutedSlide[];
}

export interface PresentationSlide {
  id: string;
  type: SlideType;
  title?: string | null;
  subtitle?: string | null;
  bullets?: string[];
  image_prompt?: string | null;
  visual_mood?: string | null;
  icon_intent?: string | null;
  notes?: string | null;
  left_title?: string | null;
  right_title?: string | null;
  left_bullets?: string[];
  right_bullets?: string[];
  timeline?: TimelineStep[];
  statistics?: StatisticItem[];
  quote?: string | null;
  attribution?: string | null;
  resolved_image?: ResolvedImageAsset | null;
}

export interface Presentation {
  title: string;
  theme: ThemeName;
  slides: PresentationSlide[];
}

export interface GeneratePresentationPayload {
  prompt: string;
  slide_count: number;
  style: string;
  template?: ThemeName;
  // "unsplash" is the backend wire value for the broader image-research pipeline.
  image_source?: "gemini" | "unsplash";
  planning_mode?: PlanningMode;
  slide_outline?: GuidedSlideIntent[];
}

export interface GeneratePresentationResponse {
  presentation: Presentation;
  layouted_presentation?: LayoutedPresentationDocument | null;
  pptx_url: string;
  pdf_url: string | null;
}

export interface ProgressState {
  value: number;
  label: string;
  stageIndex: number;
  stages: string[];
}

export type GenerationStage = "planning" | "validation" | "images" | "export";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function resolveApiAssetUrl(url: string | null | undefined): string | undefined {
  if (!url) {
    return undefined;
  }
  if (/^https?:\/\//i.test(url) || url.startsWith("data:")) {
    return url;
  }
  return `${API_BASE_URL.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

export async function generatePresentation(
  payload: GeneratePresentationPayload,
  onStage?: (stage: GenerationStage) => void,
): Promise<GeneratePresentationResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/presentations/generate-stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        "Could not reach the backend. Check whether FastAPI is still running and look at the backend terminal for a PDF export crash.",
      );
    }
    throw error;
  }

  if (!response.ok || !response.body) {
    const errorBody = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(errorBody?.detail ?? "Failed to generate presentation.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) {
        continue;
      }
      const event = JSON.parse(line) as
        | { type: "progress"; stage: GenerationStage }
        | { type: "result"; data: GeneratePresentationResponse }
        | { type: "error"; detail: string };
      if (event.type === "progress") {
        onStage?.(event.stage);
      } else if (event.type === "result") {
        return event.data;
      } else {
        throw new Error(event.detail);
      }
    }

    if (done) {
      break;
    }
  }

  throw new Error("The backend stream ended before returning a presentation.");
}

const PROGRESS_STAGES = [
  { label: "Sending prompt to the backend", value: 10 },
  { label: "Planning slides with Gemini", value: 34 },
  { label: "Validating JSON with Pydantic", value: 58 },
  { label: "Resolving slide images", value: 76 },
  { label: "Exporting PPTX and PDF", value: 92 },
];

export function createInitialProgress(): ProgressState {
  return {
    value: 0,
    label: "Waiting to start",
    stageIndex: -1,
    stages: PROGRESS_STAGES.map((stage) => stage.label),
  };
}

export function getProgressForStage(stage: GenerationStage): ProgressState {
  const stageIndex = {
    planning: 1,
    validation: 2,
    images: 3,
    export: 4,
  }[stage];
  const current = PROGRESS_STAGES[stageIndex];
  return {
    value: current.value,
    label: current.label,
    stageIndex,
    stages: PROGRESS_STAGES.map((item) => item.label),
  };
}
