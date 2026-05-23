"use client";

import { useEffect, useRef, useState } from "react";

import { PresentationPreview } from "@/components/PresentationPreview";
import { PromptForm } from "@/components/PromptForm";
import {
  GeneratePresentationPayload,
  GeneratePresentationResponse,
  ProgressState,
  createInitialProgress,
  generatePresentation,
  getProgressSnapshot,
} from "@/lib/api";


export default function HomePage() {
  const [result, setResult] = useState<GeneratePresentationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<ProgressState>(createInitialProgress());
  const requestStartedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isLoading) {
      return;
    }

    const interval = window.setInterval(() => {
      if (requestStartedAtRef.current === null) {
        return;
      }
      const elapsed = Date.now() - requestStartedAtRef.current;
      setProgress(getProgressSnapshot(elapsed));
    }, 250);

    return () => window.clearInterval(interval);
  }, [isLoading]);

  async function handleGenerate(payload: GeneratePresentationPayload) {
    setIsLoading(true);
    setError(null);
    setResult(null);
    requestStartedAtRef.current = Date.now();
    setProgress({
      ...createInitialProgress(),
      value: 6,
      label: "Preparing request",
    });

    try {
      const response = await generatePresentation(payload);
      setProgress({
        ...createInitialProgress(),
        value: 100,
        label: "Presentation ready",
        stageIndex: 4,
      });
      setResult(response);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
    } finally {
      setIsLoading(false);
      requestStartedAtRef.current = null;
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-8 px-4 py-10 sm:px-6 lg:px-8">
      <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-spark">
              AuraSlides AI
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
              Turn a rough idea into a layout-based presentation PDF.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
              The AI picks the title, content, and layout type. The backend
              keeps control of rendering, typography, spacing, and export.
            </p>
          </div>

          <PromptForm
            isLoading={isLoading}
            progressLabel={progress.label}
            progressValue={progress.value}
            onSubmit={handleGenerate}
          />
        </div>

        <PresentationPreview
          result={result}
          error={error}
          isLoading={isLoading}
          progress={progress}
        />
      </section>
    </main>
  );
}
