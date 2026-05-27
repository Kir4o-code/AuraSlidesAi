"use client";

import { FormEvent, useState } from "react";

import type { GeneratePresentationPayload } from "@/lib/api";


interface PromptFormProps {
  isLoading: boolean;
  progressLabel: string;
  progressValue: number;
  onSubmit: (payload: GeneratePresentationPayload) => Promise<void>;
}


const STYLE_OPTIONS = ["modern", "minimal", "corporate", "playful"];
const IMAGE_SOURCE_OPTIONS: Array<{
  value: GeneratePresentationPayload["image_source"];
  label: string;
}> = [
  { value: "gemini", label: "Google image AI" },
  { value: "image_research", label: "Image research" },
];


export function PromptForm({
  isLoading,
  progressLabel,
  progressValue,
  onSubmit,
}: PromptFormProps) {
  const [prompt, setPrompt] = useState(
    "Create a presentation about how small businesses can use AI to automate repetitive work while keeping a human touch.",
  );
  const [slideCount, setSlideCount] = useState(5);
  const [style, setStyle] = useState("modern");
  const [imageSource, setImageSource] =
    useState<GeneratePresentationPayload["image_source"]>("gemini");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      prompt,
      slide_count: slideCount,
      style,
      image_source: imageSource,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-card backdrop-blur"
    >
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-spark">
          Prompt
        </p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">
          Describe the presentation you want
        </h2>
      </div>

      <label className="mb-5 block">
        <span className="mb-2 block text-sm font-medium text-slate-700">
          Presentation brief
        </span>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={8}
          required
          className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-spark focus:bg-white"
          placeholder="Explain the topic, audience, and tone..."
        />
      </label>

      <div className="grid gap-4 md:grid-cols-1">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Slide count
          </span>
          <input
            type="number"
            min={3}
            max={10}
            value={slideCount}
            onChange={(event) => setSlideCount(Number(event.target.value))}
            className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-spark focus:bg-white"
          />
        </label>

        <fieldset>
          <legend className="mb-2 block text-sm font-medium text-slate-700">
            Presentation images
          </legend>
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
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="mt-6 inline-flex items-center justify-center rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isLoading ? "Generating..." : "Generate presentation"}
      </button>

      {isLoading ? (
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="font-medium text-slate-700">{progressLabel}</span>
            <span className="font-semibold text-ink">{progressValue}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-spark transition-all duration-500"
              style={{ width: `${progressValue}%` }}
            />
          </div>
        </div>
      ) : null}
    </form>
  );
}
