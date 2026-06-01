"use client";

import { useEffect, useRef, useState } from "react";
import { FiLayers, FiZap } from "react-icons/fi";

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
    <main className="relative mx-auto flex min-h-screen w-full max-w-[1480px] flex-col gap-8 overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
      <nav className="surface-panel sharp-panel relative z-10 flex items-center justify-between px-4 py-3 sm:px-5">
        <span className="inline-flex items-center gap-2 text-sm font-semibold tracking-[-0.02em] text-white">
          <span className="sharp-control flex h-8 w-8 items-center justify-center border border-white/15 bg-white/10">
            <FiZap className="h-4 w-4 text-cyan-200" aria-hidden="true" />
          </span>
          AuraSlides
        </span>
        <span className="sharp-control inline-flex items-center gap-2 border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">
          <FiLayers className="h-3.5 w-3.5" aria-hidden="true" />
          Studio
        </span>
      </nav>
      <section className="relative z-10 grid gap-6 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="space-y-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-200">
              AI presentation studio
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-0.055em] text-white sm:text-6xl">
              Sharp decks from one clear idea.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-zinc-400">
              Plan the narrative, choose the visual language, then export an
              editable presentation with a clean PDF companion.
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
