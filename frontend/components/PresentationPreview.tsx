import type { GeneratePresentationResponse, ProgressState } from "@/lib/api";

import { SlideDeck } from "@/components/presentation/SlideDeck";
import { resolveThemeTokens } from "@/lib/theme";


interface PresentationPreviewProps {
  result: GeneratePresentationResponse | null;
  error: string | null;
  isLoading: boolean;
  progress: ProgressState;
}


export function PresentationPreview({
  result,
  error,
  isLoading,
  progress,
}: PresentationPreviewProps) {
  if (error) {
    return (
      <div className="rounded-[28px] border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-card">
        <p className="text-sm font-semibold uppercase tracking-[0.2em]">
          Error
        </p>
        <p className="mt-3 text-sm leading-6">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-[28px] border border-dashed border-slate-300 bg-white/70 p-6 text-slate-500 shadow-card">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-spark">
          Preview
        </p>
        {isLoading ? (
          <>
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-spark transition-all duration-500"
                style={{ width: `${progress.value}%` }}
              />
            </div>
            <p className="mt-4 text-sm font-medium text-ink">{progress.label}</p>
            <div className="mt-4 space-y-3">
              {progress.stages.map((stage, index) => {
                const isComplete = index < progress.stageIndex;
                const isActive = index === progress.stageIndex;

                return (
                  <div
                    key={stage}
                    className={`rounded-2xl border px-4 py-3 text-sm transition ${
                      isActive
                        ? "border-teal-300 bg-teal-50 text-ink"
                        : isComplete
                          ? "border-slate-200 bg-white text-slate-600"
                          : "border-slate-200 bg-white/70 text-slate-400"
                    }`}
                  >
                    {stage}
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <p className="mt-3 text-sm leading-6">
            Generated presentation JSON and the PDF download link will appear
            here.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-card backdrop-blur">
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-spark">
            Result
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-ink">
            {result.presentation.title}
          </h2>
        </div>

        <div className="flex flex-wrap gap-3">
          <a
            href={result.pptx_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-ink transition hover:border-slate-400 hover:bg-slate-50"
          >
            Download PPTX
          </a>
          <a
            href={result.pdf_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-ink transition hover:border-slate-400 hover:bg-slate-50"
          >
            Download PDF
          </a>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
            Theme
          </p>
          <p className="mt-2 text-sm font-medium text-ink">
            {result.presentation.theme}
          </p>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
            Background
          </p>
          <p className="mt-2 text-sm font-medium text-ink">
            {resolveThemeTokens(result.presentation.theme).background}
          </p>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
            Font
          </p>
          <p className="mt-2 text-sm font-medium text-ink">
            {resolveThemeTokens(result.presentation.theme).fontFamily}
          </p>
        </div>
      </div>

      <div className="mt-6 rounded-[30px] border border-slate-200 bg-slate-50 p-4">
        <SlideDeck presentation={result.presentation} />
      </div>
    </div>
  );
}
