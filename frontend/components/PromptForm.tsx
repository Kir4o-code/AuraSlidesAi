"use client";

import { FormEvent, useState } from "react";

import { GuidedSlidePlanner } from "@/components/GuidedSlidePlanner";
import { TemplateSelector } from "@/components/TemplateSelector";
import type { GeneratePresentationPayload, GuidedSlideIntent, PlanningMode, ThemeName } from "@/lib/api";

interface PromptFormProps {
  isLoading: boolean;
  progressLabel: string;
  progressValue: number;
  onSubmit: (payload: GeneratePresentationPayload) => Promise<void>;
}

const IMAGE_SOURCE_OPTIONS: Array<{
  value: GeneratePresentationPayload["image_source"];
  label: string;
}> = [
  { value: "gemini", label: "Google image AI" },
  { value: "image_research", label: "Image research" },
];

const INITIAL_GUIDED_SLIDES: GuidedSlideIntent[] = [
  {
    purpose: "Introduce the topic and explain why it matters to the audience.",
    requested_type: "title_slide",
  },
  {
    purpose: "Explain the most important ideas, facts, or mechanisms clearly.",
    requested_type: null,
  },
  {
    purpose: "Conclude with the clearest takeaway and practical next step.",
    requested_type: "quote",
  },
];

const WIZARD_STEPS = [
  { id: 1, title: "Prompt", subtitle: "Start with the idea" },
  { id: 2, title: "Theme", subtitle: "Pick a visual style" },
  { id: 3, title: "Planning", subtitle: "Choose automatic or guided" },
  { id: 4, title: "Images", subtitle: "Set the image source" },
] as const;

export function PromptForm({ isLoading, progressLabel, progressValue, onSubmit }: PromptFormProps) {
  const [prompt, setPrompt] = useState(
    "Create a presentation about how small businesses can use AI to automate repetitive work while keeping a human touch.",
  );
  const [slideCount, setSlideCount] = useState(5);
  const [template, setTemplate] = useState<ThemeName>("clean_school");
  const [planningMode, setPlanningMode] = useState<PlanningMode>("automatic");
  const [guidedSlides, setGuidedSlides] = useState<GuidedSlideIntent[]>(INITIAL_GUIDED_SLIDES);
  const [imageSource, setImageSource] = useState<GeneratePresentationPayload["image_source"]>("gemini");
  const [step, setStep] = useState(1);

  function goNext() {
    setStep((current) => Math.min(current + 1, WIZARD_STEPS.length));
  }

  function goBack() {
    setStep((current) => Math.max(current - 1, 1));
  }

  const isFinalStep = step === WIZARD_STEPS.length;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      prompt,
      slide_count: planningMode === "guided" ? guidedSlides.length : slideCount,
      style: template,
      template,
      image_source: imageSource,
      planning_mode: planningMode,
      slide_outline: planningMode === "guided" ? guidedSlides : undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-card backdrop-blur">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-spark">Prompt flow</p>
          <h2 className="mt-2 text-2xl font-semibold text-ink">Build the deck step by step</h2>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
          <span>{step}</span>
          <span>/</span>
          <span>{WIZARD_STEPS.length}</span>
        </div>
      </div>

      <div className="mb-5 grid gap-2 sm:grid-cols-4">
        {WIZARD_STEPS.map((item) => {
          const active = step === item.id;
          const complete = step > item.id;
          return (
            <button
              key={item.id}
              type="button"
              disabled={isLoading}
              onClick={() => setStep(item.id)}
              className={`rounded-2xl border px-3 py-3 text-left transition ${
                active
                  ? "border-spark bg-teal-50 ring-2 ring-spark/15"
                  : complete
                    ? "border-emerald-200 bg-emerald-50/70 hover:bg-emerald-50"
                    : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
              } disabled:cursor-not-allowed disabled:opacity-60`}
            >
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-slate-500">Step {item.id}</p>
              <p className="mt-1 text-sm font-semibold text-ink">{item.title}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{item.subtitle}</p>
            </button>
          );
        })}
      </div>

      {step === 1 ? (
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">Presentation brief</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={8}
            required
            className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-spark focus:bg-white"
            placeholder="Explain the topic, audience, and tone..."
          />
        </label>
      ) : null}

      {step === 2 ? <TemplateSelector disabled={isLoading} value={template} onChange={setTemplate} /> : null}

      {step === 3 ? (
        <fieldset className="mb-5">
          <legend className="mb-2 block text-sm font-medium text-slate-700">Content planning</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              {
                value: "automatic" as const,
                label: "Plan whole deck",
                description: "AI structures the complete story from your brief.",
              },
              {
                value: "guided" as const,
                label: "Guide each slide",
                description: "Add compact notes so every slide has a distinct job.",
              },
            ].map((option) => {
              const active = planningMode === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={isLoading}
                  onClick={() => setPlanningMode(option.value)}
                  aria-pressed={active}
                  className={`rounded-2xl border p-4 text-left transition ${
                    active
                      ? "border-spark bg-teal-50 ring-2 ring-spark/15"
                      : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
                  } disabled:opacity-60`}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <span
                      className={`h-4 w-4 rounded-full border ${
                        active ? "border-spark bg-spark shadow-[inset_0_0_0_3px_white]" : "border-slate-300 bg-white"
                      }`}
                    />
                    {option.label}
                  </span>
                  <span className="mt-2 block text-xs leading-5 text-slate-500">{option.description}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
            {planningMode === "automatic" ? (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Slide count</span>
                <input
                  type="number"
                  min={3}
                  max={10}
                  value={slideCount}
                  onChange={(event) => setSlideCount(Number(event.target.value))}
                  className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-spark focus:bg-white"
                />
              </label>
            ) : (
              <GuidedSlidePlanner disabled={isLoading} slides={guidedSlides} onChange={setGuidedSlides} />
            )}
          </div>
        </fieldset>
      ) : null}

      {step === 4 ? (
        <fieldset>
          <legend className="mb-2 block text-sm font-medium text-slate-700">Presentation images</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {IMAGE_SOURCE_OPTIONS.map((option) => {
              const active = imageSource === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={isLoading}
                  onClick={() => setImageSource(option.value)}
                  className={`rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
                    active
                      ? "border-ink bg-ink text-white"
                      : "border-slate-300 bg-slate-50 text-slate-700 hover:bg-white disabled:opacity-60"
                  }`}
                  aria-pressed={active}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          disabled={isLoading || step === 1}
          onClick={goBack}
          className="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Back
        </button>

        {isFinalStep ? (
          <button
            type="submit"
            disabled={isLoading}
            className="inline-flex items-center justify-center rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Generating..." : "Generate presentation"}
          </button>
        ) : (
          <button
            type="button"
            disabled={isLoading}
            onClick={goNext}
            className="inline-flex items-center justify-center rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="font-medium text-slate-700">{progressLabel}</span>
            <span className="font-semibold text-ink">{progressValue}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full bg-spark transition-all duration-500" style={{ width: `${progressValue}%` }} />
          </div>
        </div>
      ) : null}
    </form>
  );
}
