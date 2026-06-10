import { SlideDeck } from "@/components/presentation/SlideDeck";
import type { LayoutedPresentationDocument, Presentation } from "@/lib/api";
import { resolveApiAssetUrl } from "@/lib/api";

interface ExportPageProps {
  params: Promise<{
    assetId: string;
  }>;
  searchParams: Promise<{
    slide?: string;
  }>;
}

interface ExportPayload {
  presentation: Presentation;
  layouted_presentation?: LayoutedPresentationDocument | null;
}

async function loadPresentation(assetId: string): Promise<ExportPayload> {
  const response = await fetch(resolveApiAssetUrl(`/generated/export_data/${assetId}.json`) ?? "", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Export data request failed with ${response.status}.`);
  }

  const data = (await response.json()) as Presentation | ExportPayload;
  return "presentation" in data ? data : { presentation: data };
}

export default async function ExportPage({ params, searchParams }: ExportPageProps) {
  const [{ assetId }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const { presentation, layouted_presentation: layoutedPresentation } = await loadPresentation(assetId);
  const parsedSlide = Number(resolvedSearchParams.slide);
  const slideIndex = Number.isInteger(parsedSlide) && parsedSlide >= 0 ? parsedSlide : null;
  const visiblePresentation =
    slideIndex === null
      ? presentation
      : {
          ...presentation,
          slides: presentation.slides.slice(slideIndex, slideIndex + 1),
        };
  const visibleLayoutedPresentation =
    slideIndex === null
      ? layoutedPresentation
      : layoutedPresentation
        ? {
            ...layoutedPresentation,
            slides: layoutedPresentation.slides.slice(slideIndex, slideIndex + 1),
          }
        : null;

  return (
    <main className={slideIndex === null ? "export-page export-page--deck" : "export-page export-page--single"}>
      <SlideDeck presentation={visiblePresentation} layoutedPresentation={visibleLayoutedPresentation} exportMode />
    </main>
  );
}
