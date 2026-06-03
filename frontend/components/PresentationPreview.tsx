import type { GeneratePresentationResponse, ProgressState } from "@/lib/api";
import { FiAlertTriangle, FiDownload, FiFileText, FiLoader, FiMonitor } from "react-icons/fi";

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
      <div className="surface-panel sharp-panel p-6 text-rose-200">
        <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em]">
          <FiAlertTriangle className="h-4 w-4" aria-hidden="true" />
          Error
        </p>
        <p className="mt-3 text-sm leading-6">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="surface-panel sharp-panel p-6 text-zinc-500">
        <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-200">
          <FiMonitor className="h-4 w-4" aria-hidden="true" />
          Preview
        </p>
        {isLoading ? (
          <>
            <div className="mt-4 h-3 overflow-hidden bg-white/10">
              <div
                className="h-full bg-white transition-all duration-500"
                style={{ width: `${progress.value}%` }}
              />
            </div>
            <p className="mt-4 flex items-center gap-2 text-sm font-medium text-white">
              <FiLoader className="h-4 w-4 animate-spin text-cyan-200" aria-hidden="true" />
              {progress.label}
            </p>
            <div className="mt-4 space-y-3">
              {progress.stages.map((stage, index) => {
                const isComplete = index < progress.stageIndex;
                const isActive = index === progress.stageIndex;

                return (
                  <div
                    key={stage}
                    className={`sharp-control border px-4 py-3 text-sm transition ${
                      isActive
                        ? "border-cyan-300/50 bg-cyan-300/10 text-white"
                        : isComplete
                          ? "border-white/15 bg-white/[0.07] text-zinc-300"
                          : "border-white/10 bg-white/[0.03] text-zinc-600"
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
            Your generated deck, export links, and slide navigator appear here.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="surface-panel sharp-panel min-h-screen p-6 sm:p-8">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-200">
            Result
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-white">
            {result.presentation.title}
          </h2>
        </div>

        <div className="flex flex-wrap gap-3">
          <a
            href={result.pptx_url}
            target="_blank"
            rel="noreferrer"
            className="button-press interactive-outline sharp-control inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white [--control-bg:#101012] hover:[--control-bg:#18181b]"
          >
            <FiDownload className="h-4 w-4" aria-hidden="true" />
            Download PPTX
          </a>
          {result.pdf_url ? (
            <a
              href={result.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="button-press interactive-outline sharp-control inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white [--control-bg:#18181b] hover:[--control-bg:#202024]"
            >
              <FiFileText className="h-4 w-4" aria-hidden="true" />
              Download PDF
            </a>
          ) : (
            <span className="sharp-control inline-flex items-center justify-center border border-white/10 px-4 py-2.5 text-sm font-semibold text-zinc-600">
              PDF unavailable
            </span>
          )}
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <div className="sharp-control border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
            Theme
          </p>
          <p className="mt-2 text-sm font-medium text-white">
            {result.presentation.theme}
          </p>
        </div>
        <div className="sharp-control border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
            Background
          </p>
          <p className="mt-2 text-sm font-medium text-white">
            {resolveThemeTokens(result.presentation.theme).background}
          </p>
        </div>
        <div className="sharp-control border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
            Font
          </p>
          <p className="mt-2 text-sm font-medium text-white">
            {resolveThemeTokens(result.presentation.theme).fontFamily}
          </p>
        </div>
      </div>

      <div className="sharp-panel mt-6 border border-white/10 bg-black/30 p-3">
        <SlideDeck presentation={result.presentation} layoutedPresentation={result.layouted_presentation ?? null} />
      </div>
    </div>
  );
}
