"use client";

import { FormEvent, useState } from "react";
import { FiArrowLeft, FiArrowRight, FiCpu, FiImage, FiLayers, FiZap } from "react-icons/fi";

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
  { id: 1, title: "Prompt", subtitle: "Start with the idea", icon: FiZap },
  { id: 2, title: "Theme", subtitle: "Pick a visual style", icon: FiLayers },
  { id: 3, title: "Planning", subtitle: "Shape the narrative", icon: FiCpu },
  { id: 4, title: "Images", subtitle: "Set the visual source", icon: FiImage },
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
    <form onSubmit={handleSubmit} className="surface-panel sharp-panel p-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-200">Prompt flow</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-white">Build the deck step by step</h2>
        </div>
        <div className="sharp-control flex items-center gap-2 border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-zinc-300">
          <span>{step}</span>
          <span>/</span>
          <span>{WIZARD_STEPS.length}</span>
        </div>
      </div>

      <div className="mb-5 grid gap-2 sm:grid-cols-4">
        {WIZARD_STEPS.map((item) => {
          const active = step === item.id;
          const complete = step > item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              disabled={isLoading}
              onClick={() => setStep(item.id)}
              className={`button-press interactive-outline sharp-control px-3 py-3 text-left ${
                active
                  ? "[--control-bg:#18181b] shadow-[0_0_22px_rgba(34,211,238,0.08)]"
                  : complete
                    ? "[--control-bg:#141416] hover:[--control-bg:#19191c]"
                    : "[--control-bg:#0f0f11] hover:[--control-bg:#17171a]"
              } disabled:cursor-not-allowed disabled:opacity-60`}
            >
              <Icon className={`h-4 w-4 ${active ? "text-cyan-200" : "text-zinc-500"}`} aria-hidden="true" />
              <p className="mt-3 text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-zinc-500">Step {item.id}</p>
              <p className="mt-1 text-sm font-semibold text-white">{item.title}</p>
              <p className="mt-1 text-xs leading-5 text-zinc-500">{item.subtitle}</p>
            </button>
          );
        })}
      </div>

      {step === 1 ? (
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-zinc-300">Presentation brief</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={8}
            required
            className="sharp-control w-full border border-white/10 bg-black/35 px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-zinc-600 focus:border-cyan-300/70 focus:bg-black/55"
            placeholder="Explain the topic, audience, and tone..."
          />
        </label>
      ) : null}

      {step === 2 ? <TemplateSelector disabled={isLoading} value={template} onChange={setTemplate} /> : null}

      {step === 3 ? (
        <fieldset className="mb-5">
          <legend className="mb-2 block text-sm font-medium text-zinc-300">Content planning</legend>
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
                  className={`button-press interactive-outline sharp-control p-4 text-left ${
                    active
                      ? "[--control-bg:#18181b]"
                      : "[--control-bg:#0f0f11] hover:[--control-bg:#17171a]"
                  } disabled:opacity-60`}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-white">
                    <span
                      className={`h-4 w-4 rounded-full border ${
                        active ? "border-cyan-200 bg-cyan-200 shadow-[inset_0_0_0_3px_#09090b]" : "border-zinc-600 bg-black"
                      }`}
                    />
                    {option.label}
                  </span>
                  <span className="mt-2 block text-xs leading-5 text-zinc-500">{option.description}</span>
                </button>
              );
            })}
          </div>

          <div className="sharp-control mt-4 border border-white/10 bg-black/25 p-4">
            {planningMode === "automatic" ? (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-zinc-300">Slide count</span>
                <input
                  type="number"
                  min={3}
                  max={10}
                  value={slideCount}
                  onChange={(event) => setSlideCount(Number(event.target.value))}
                  className="sharp-control w-full border border-white/10 bg-black/35 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/70"
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
          <legend className="mb-2 block text-sm font-medium text-zinc-300">Presentation images</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {IMAGE_SOURCE_OPTIONS.map((option) => {
              const active = imageSource === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={isLoading}
                  onClick={() => setImageSource(option.value)}
                  className={`button-press interactive-outline sharp-control px-4 py-3 text-sm font-semibold ${
                    active
                      ? "[--control-bg:#18181b] text-white"
                      : "[--control-bg:#0f0f11] text-zinc-400 hover:[--control-bg:#17171a] disabled:opacity-60"
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
          className="button-press interactive-outline sharp-control inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold text-zinc-300 [--control-bg:#101012] hover:[--control-bg:#18181b] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back
        </button>

        {isFinalStep ? (
          <button
            type="submit"
            disabled={isLoading}
            className="button-press interactive-outline sharp-control inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold text-white [--control-bg:#18181b] hover:[--control-bg:#202024] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiZap className="h-4 w-4" aria-hidden="true" />
            {isLoading ? "Generating..." : "Generate presentation"}
          </button>
        ) : (
          <button
            type="button"
            disabled={isLoading}
            onClick={goNext}
            className="button-press interactive-outline sharp-control inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold text-white [--control-bg:#18181b] hover:[--control-bg:#202024] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
            <FiArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="sharp-control mt-5 border border-white/10 bg-white/[0.03] p-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="font-medium text-zinc-300">{progressLabel}</span>
            <span className="font-semibold text-white">{progressValue}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden bg-white/10">
            <div className="h-full bg-white transition-all duration-500" style={{ width: `${progressValue}%` }} />
          </div>
        </div>
      ) : null}
    </form>
  );
}
