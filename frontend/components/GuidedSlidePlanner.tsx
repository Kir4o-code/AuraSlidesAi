import type { GuidedSlideIntent, SlideType } from "@/lib/api";
import { FiPlus, FiTrash2 } from "react-icons/fi";

interface GuidedSlidePlannerProps {
  disabled?: boolean;
  slides: GuidedSlideIntent[];
  onChange: (slides: GuidedSlideIntent[]) => void;
}

const SLIDE_TYPE_OPTIONS: Array<{ value: SlideType | ""; label: string }> = [
  { value: "", label: "AI chooses layout" },
  { value: "title_slide", label: "Opening title" },
  { value: "title_bullets", label: "Key points" },
  { value: "title_bullets_image", label: "Points with image" },
  { value: "hero_image", label: "Image-led story" },
  { value: "comparison", label: "Comparison" },
  { value: "timeline", label: "Timeline or steps" },
  { value: "statistics", label: "Statistics" },
  { value: "quote", label: "Conclusion or quote" },
];

export function GuidedSlidePlanner({ disabled, slides, onChange }: GuidedSlidePlannerProps) {
  function updateSlide(index: number, patch: Partial<GuidedSlideIntent>) {
    onChange(slides.map((slide, slideIndex) => (slideIndex === index ? { ...slide, ...patch } : slide)));
  }

  function removeSlide(index: number) {
    if (slides.length <= 3) {
      return;
    }
    onChange(slides.filter((_, slideIndex) => slideIndex !== index));
  }

  function addSlide() {
    if (slides.length >= 10) {
      return;
    }
    onChange([...slides, { purpose: "", requested_type: null }]);
  }

  return (
    <section className="sharp-control border border-white/10 bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">Build the story slide by slide</p>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            Give each slide one job. AI expands the note into concise presentation content.
          </p>
        </div>
        <span className="sharp-control border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-zinc-300">
          {slides.length} slides
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {slides.map((slide, index) => (
          <article key={index} className="sharp-control border border-white/10 bg-black/30 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                Slide {index + 1}
              </p>
              <button
                type="button"
                disabled={disabled || slides.length <= 3}
                onClick={() => removeSlide(index)}
                className="button-press interactive-outline sharp-control inline-flex items-center gap-1.5 px-2 py-1 text-xs font-semibold text-zinc-400 [--control-bg:#101012] hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-30"
              >
                <FiTrash2 className="h-3.5 w-3.5" aria-hidden="true" />
                Remove
              </button>
            </div>
            <label className="mt-3 block">
              <span className="mb-1.5 block text-xs font-medium text-zinc-400">What should this slide accomplish?</span>
              <textarea
                value={slide.purpose}
                onChange={(event) => updateSlide(index, { purpose: event.target.value })}
                rows={3}
                required
                disabled={disabled}
                className="sharp-control w-full border border-white/10 bg-black/35 px-3 py-2 text-sm leading-6 text-white outline-none transition focus:border-cyan-300/70"
              />
            </label>
            <label className="mt-3 block">
              <span className="mb-1.5 block text-xs font-medium text-zinc-400">Layout preference</span>
              <select
                value={slide.requested_type ?? ""}
                onChange={(event) => updateSlide(index, { requested_type: (event.target.value || null) as SlideType | null })}
                disabled={disabled}
                className="sharp-control w-full border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 outline-none transition focus:border-cyan-300/70"
              >
                {SLIDE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value || "automatic"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </article>
        ))}
      </div>

      <button
        type="button"
        disabled={disabled || slides.length >= 10}
        onClick={addSlide}
        className="button-press interactive-outline sharp-control mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-cyan-200 [--control-bg:#101012] hover:[--control-bg:#18181b] disabled:cursor-not-allowed disabled:opacity-40"
      >
        <FiPlus className="h-4 w-4" aria-hidden="true" />
        Add slide
      </button>
    </section>
  );
}
