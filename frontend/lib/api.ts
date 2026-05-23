export type LayoutName =
  | "title"
  | "bullets"
  | "bullets_with_image"
  | "image_focus"
  | "conclusion";

export type ImageRole =
  | "background_image"
  | "main_object"
  | "icon"
  | "diagram";

export interface ImageSpec {
  query: string;
  role: ImageRole;
  remove_background: boolean;
}

export interface Theme {
  style: string;
  primary_color: string;
  font: string;
}

export interface TitleSlide {
  layout: "title";
  title: string;
  subtitle: string;
}

export interface BulletsSlide {
  layout: "bullets";
  title: string;
  bullets: string[];
}

export interface BulletsWithImageSlide {
  layout: "bullets_with_image";
  title: string;
  bullets: string[];
  image: ImageSpec;
}

export interface ImageFocusSlide {
  layout: "image_focus";
  title: string;
  caption: string;
  image: ImageSpec;
}

export interface ConclusionSlide {
  layout: "conclusion";
  title: string;
  bullets: string[];
  closing: string;
}

export type Slide =
  | TitleSlide
  | BulletsSlide
  | BulletsWithImageSlide
  | ImageFocusSlide
  | ConclusionSlide;

export interface Presentation {
  title: string;
  theme: Theme;
  slides: Slide[];
}

export interface GeneratePresentationPayload {
  prompt: string;
  slide_count: number;
  style: string;
  generate_images?: boolean;
}

export interface GeneratePresentationResponse {
  presentation: Presentation;
  pdf_url: string;
}

export interface ProgressState {
  value: number;
  label: string;
  stageIndex: number;
  stages: string[];
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function generatePresentation(
  payload: GeneratePresentationPayload,
): Promise<GeneratePresentationResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/presentations/generate`, {
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

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(errorBody?.detail ?? "Failed to generate presentation.");
  }

  return (await response.json()) as GeneratePresentationResponse;
}

const PROGRESS_STAGES = [
  { label: "Sending prompt to the backend", value: 10 },
  { label: "Planning slides with Gemini", value: 34 },
  { label: "Validating JSON with Pydantic", value: 58 },
  { label: "Generating slide images with Gemini", value: 76 },
  { label: "Exporting the PDF", value: 92 },
];

export function createInitialProgress(): ProgressState {
  return {
    value: 0,
    label: "Waiting to start",
    stageIndex: -1,
    stages: PROGRESS_STAGES.map((stage) => stage.label),
  };
}

export function getProgressSnapshot(elapsedMs: number): ProgressState {
  if (elapsedMs <= 0) {
    return createInitialProgress();
  }

  const timeline = [
    { maxMs: 500, stageIndex: 0 },
    { maxMs: 3500, stageIndex: 1 },
    { maxMs: 5000, stageIndex: 2 },
    { maxMs: 7000, stageIndex: 3 },
    { maxMs: Number.POSITIVE_INFINITY, stageIndex: 4 },
  ];

  const active = timeline.find((item) => elapsedMs <= item.maxMs) ?? timeline[timeline.length - 1];
  const stage = PROGRESS_STAGES[active.stageIndex];
  const previousValue = active.stageIndex === 0 ? 0 : PROGRESS_STAGES[active.stageIndex - 1].value;
  const stageStartMs = active.stageIndex === 0 ? 0 : timeline[active.stageIndex - 1].maxMs;
  const stageEndMs = active.maxMs === Number.POSITIVE_INFINITY ? stageStartMs + 4000 : active.maxMs;
  const stageDuration = Math.max(stageEndMs - stageStartMs, 1);
  const stageElapsed = Math.max(elapsedMs - stageStartMs, 0);
  const stageProgress = Math.min(stageElapsed / stageDuration, 1);
  const value = Math.min(
    Math.round(previousValue + (stage.value - previousValue) * stageProgress),
    95,
  );

  return {
    value,
    label: stage.label,
    stageIndex: active.stageIndex,
    stages: PROGRESS_STAGES.map((item) => item.label),
  };
}
