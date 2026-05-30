import type { GuidedSlideIntent, SlideType } from "@/lib/api";

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
    <section className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Build the story slide by slide</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Give each slide one job. AI expands the note into concise presentation content.
          </p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600">
          {slides.length} slides
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {slides.map((slide, index) => (
          <article key={index} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-spark">
                Slide {index + 1}
              </p>
              <button
                type="button"
                disabled={disabled || slides.length <= 3}
                onClick={() => removeSlide(index)}
                className="text-xs font-semibold text-slate-400 transition hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Remove
              </button>
            </div>
            <label className="mt-3 block">
              <span className="mb-1.5 block text-xs font-medium text-slate-600">What should this slide accomplish?</span>
              <textarea
                value={slide.purpose}
                onChange={(event) => updateSlide(index, { purpose: event.target.value })}
                rows={3}
                required
                disabled={disabled}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 outline-none transition focus:border-spark focus:bg-white"
              />
            </label>
            <label className="mt-3 block">
              <span className="mb-1.5 block text-xs font-medium text-slate-600">Layout preference</span>
              <select
                value={slide.requested_type ?? ""}
                onChange={(event) => updateSlide(index, { requested_type: (event.target.value || null) as SlideType | null })}
                disabled={disabled}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-spark"
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
        className="mt-4 inline-flex items-center gap-2 rounded-full border border-dashed border-spark/60 bg-white px-4 py-2 text-sm font-semibold text-spark transition hover:border-spark hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <span className="text-lg leading-none">+</span>
        Add slide
      </button>
    </section>
  );
}
