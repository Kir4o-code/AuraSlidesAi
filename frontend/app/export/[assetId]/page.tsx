import { SlideDeck } from "@/components/presentation/SlideDeck";
import type { Presentation } from "@/lib/api";
import { resolveApiAssetUrl } from "@/lib/api";

interface ExportPageProps {
  params: Promise<{
    assetId: string;
  }>;
  searchParams: Promise<{
    slide?: string;
  }>;
}

async function loadPresentation(assetId: string): Promise<Presentation> {
  const response = await fetch(resolveApiAssetUrl(`/generated/export_data/${assetId}.json`) ?? "", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Export data request failed with ${response.status}.`);
  }

  return (await response.json()) as Presentation;
}

export default async function ExportPage({ params, searchParams }: ExportPageProps) {
  const [{ assetId }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const presentation = await loadPresentation(assetId);
  const parsedSlide = Number(resolvedSearchParams.slide);
  const slideIndex = Number.isInteger(parsedSlide) && parsedSlide >= 0 ? parsedSlide : null;
  const visiblePresentation =
    slideIndex === null
      ? presentation
      : {
          ...presentation,
          slides: presentation.slides.slice(slideIndex, slideIndex + 1),
        };

  return (
    <main className={slideIndex === null ? "export-page export-page--deck" : "export-page export-page--single"}>
      <SlideDeck presentation={visiblePresentation} exportMode />
    </main>
  );
}
