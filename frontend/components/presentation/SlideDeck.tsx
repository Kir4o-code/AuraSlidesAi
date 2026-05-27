import type { CSSProperties, ReactElement, ReactNode } from "react";

import type {
  LayoutElement,
  LayoutedPresentationDocument,
  LayoutedSlide,
  Presentation,
  PresentationSlide,
  SlideType,
} from "@/lib/api";
import { resolveApiAssetUrl } from "@/lib/api";
import { buildThemeStyle, resolveThemeTokens } from "@/lib/theme";

const SHOW_LAYOUT_DEBUG = process.env.NEXT_PUBLIC_LAYOUT_DEBUG === "true";

interface SlideRendererProps {
  slide: PresentationSlide;
  presentation: Presentation;
  exportMode?: boolean;
}

function SlideShell({
  tokens,
  accentLabel,
  exportMode,
  positioned = false,
  children,
}: {
  tokens: ReturnType<typeof resolveThemeTokens>;
  accentLabel: string;
  exportMode?: boolean;
  positioned?: boolean;
  children: ReactNode;
}) {
  const themeStyle = buildThemeStyle(tokens) as CSSProperties;

  return (
    <article
      className={`relative h-full w-full overflow-hidden rounded-[32px] border shadow-[0_28px_80px_rgba(15,23,42,0.12)] ${exportMode ? "print:shadow-none" : ""}`}
      style={{
        ...themeStyle,
        padding: positioned ? 0 : `calc(2.5rem * ${tokens.spacingScale})`,
        background: `linear-gradient(145deg, ${tokens.background} 0%, ${tokens.backgroundAlt} 100%)`,
        borderColor: tokens.borderColor,
        boxShadow: tokens.shadow,
        color: tokens.textColor,
        fontFamily: tokens.bodyFontFamily,
      }}
    >
      <div
        className="absolute inset-y-0 left-0 w-2"
        style={{ background: `linear-gradient(180deg, ${tokens.accentColor}, ${tokens.accentSoftColor})` }}
      />
      <div
        className="absolute right-8 top-8 h-40 w-40 rounded-full blur-3xl opacity-50"
        style={{ background: `${tokens.accentColor}26` }}
      />
      <div className="relative z-10 flex h-full flex-col gap-10">
        <div className="flex-1">{children}</div>
      </div>
    </article>
  );
}

function layoutFontFamily(tokens: ReturnType<typeof resolveThemeTokens>, element: LayoutElement) {
  const region = element.region.toLowerCase();
  if (element.kind === "quote" || element.kind === "statistic") {
    return tokens.headingFontFamily;
  }
  if (region.includes("title") || region.includes("quote") || region.includes("heading")) {
    return tokens.headingFontFamily;
  }
  return tokens.bodyFontFamily;
}

function DeckIcon({ icon, tokens }: { icon: string; tokens: ReturnType<typeof resolveThemeTokens> }) {
  const stroke = tokens.accentColor;
  return (
    <svg viewBox="0 0 48 48" className="h-full w-full" aria-hidden="true">
      <circle cx="24" cy="24" r="22" fill={tokens.accentSoftColor} stroke={stroke} strokeWidth="2" />
      {icon === "chart" ? (
        <>
          <rect x="15" y="25" width="4" height="10" rx="1" fill={stroke} />
          <rect x="22" y="19" width="4" height="16" rx="1" fill={stroke} />
          <rect x="29" y="14" width="4" height="21" rx="1" fill={stroke} />
        </>
      ) : icon === "bolt" ? (
        <path d="M27 10 16 27h8l-3 11 12-18h-8l2-10Z" fill={stroke} />
      ) : icon === "idea" ? (
        <>
          <circle cx="24" cy="21" r="8" fill={stroke} />
          <rect x="20" y="30" width="8" height="5" rx="2" fill={stroke} />
        </>
      ) : (
        <>
          <circle cx="24" cy="24" r="10" fill="none" stroke={stroke} strokeWidth="3" />
          <circle cx="24" cy="24" r="3" fill={stroke} />
        </>
      )}
    </svg>
  );
}

function LayoutElementRenderer({
  element,
  tokens,
  debug,
}: {
  element: LayoutElement;
  tokens: ReturnType<typeof resolveThemeTokens>;
  debug?: boolean;
}) {
  const align = element.align === "center" ? "center" : element.align === "end" ? "right" : "left";
  const style: CSSProperties = {
    position: "absolute",
    left: element.x,
    top: element.y,
    width: element.width,
    height: element.height,
    fontFamily: layoutFontFamily(tokens, element),
    fontSize: element.font_size ? `${element.font_size}px` : undefined,
    lineHeight: element.line_height ?? undefined,
    textAlign: align,
    color: tokens.textColor,
    overflow: "hidden",
  };

  const content = element.content as Record<string, unknown>;

  if (content.decorative_icon) {
    return (
      <div style={style}>
        <DeckIcon icon={(content.icon as string | undefined) ?? "target"} tokens={tokens} />
      </div>
    );
  }

  if (element.kind === "panel") {
    return (
      <div
        style={{
          ...style,
          background: tokens.surface,
          border: `1px solid ${tokens.borderColor}`,
          borderRadius: 24,
          padding: 24,
          boxShadow: tokens.shadow,
        }}
      >
        {element.children.map((child) => (
          <LayoutElementRenderer key={child.id} element={child} tokens={tokens} debug={debug} />
        ))}
        {debug ? (
          <div className="pointer-events-none absolute inset-0 rounded-[24px] border border-dashed border-rose-500/70" />
        ) : null}
      </div>
    );
  }

  if (element.kind === "image") {
    const imageUrl = resolveApiAssetUrl((content.src as string | undefined) ?? (content.public_url as string | undefined));
    const alt = (content.alt as string | undefined) ?? element.text ?? "Image";

    return (
      <div
        style={{
          ...style,
          borderRadius: 24,
          border: `1px solid ${tokens.borderColor}`,
          background: `linear-gradient(180deg, ${tokens.surface}, ${tokens.backgroundAlt})`,
        }}
      >
        {imageUrl ? (
          <img src={imageUrl} alt={alt} className="h-full w-full rounded-[24px] object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center p-5 text-center text-sm leading-6" style={{ color: tokens.textColor }}>
            {(content.prompt as string | undefined) ?? alt}
          </div>
        )}
      </div>
    );
  }

  if (element.kind === "bullet_list") {
    return (
      <div style={style}>
        {element.children.map((child) => (
          <LayoutElementRenderer key={child.id} element={child} tokens={tokens} debug={debug} />
        ))}
      </div>
    );
  }

  if (element.kind === "bullet_item") {
    return (
      <div
        style={{
          ...style,
          display: "flex",
          alignItems: "flex-start",
          gap: 16,
          padding: 16,
          borderRadius: 20,
          border: `1px solid ${tokens.borderColor}`,
          background: `${tokens.surface}d9`,
        }}
      >
        <span className="h-12 w-12 flex-none">
          <DeckIcon icon={(content.icon as string | undefined) ?? "target"} tokens={tokens} />
        </span>
        <span style={{ flex: 1 }}>{element.text}</span>
      </div>
    );
  }

  return (
    <div style={style}>
      {element.text}
      {element.children.map((child) => (
        <LayoutElementRenderer key={child.id} element={child} tokens={tokens} debug={debug} />
      ))}
      {debug ? (
        <div className="pointer-events-none absolute inset-0 border border-dashed border-rose-500/70" />
      ) : null}
    </div>
  );
}

function LayoutedSlideRenderer({
  slide,
  layoutedSlide,
  presentation,
  exportMode,
}: {
  slide: PresentationSlide;
  layoutedSlide: LayoutedSlide;
  presentation: Presentation;
  exportMode?: boolean;
}) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel={layoutedSlide.layout_name} exportMode={exportMode} positioned>
      <div className="absolute inset-0">
        {layoutedSlide.elements.map((element) => (
          <LayoutElementRenderer key={element.id} element={element} tokens={tokens} debug={SHOW_LAYOUT_DEBUG || layoutedSlide.debug_mode} />
        ))}
      </div>
    </SlideShell>
  );
}

function SlideImage({ slide, tokens, exportMode }: SlideRendererProps & { tokens: ReturnType<typeof resolveThemeTokens> }) {
  const imageUrl = resolveApiAssetUrl(slide.resolved_image?.public_url);
  const alt = slide.resolved_image?.image_url ?? slide.image_prompt ?? slide.title ?? slide.type;

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={alt}
        className={`h-full w-full rounded-[24px] object-cover ${exportMode ? "print:object-contain" : ""}`}
        style={{ border: `1px solid ${tokens.borderColor}` }}
      />
    );
  }

  return (
    <div
      className="flex h-full min-h-0 items-center justify-center rounded-[24px] p-5 text-center"
      style={{
        border: `1px dashed ${tokens.borderColor}`,
        background: `linear-gradient(180deg, ${tokens.surface}, ${tokens.backgroundAlt})`,
      }}
    >
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.22em]" style={{ color: tokens.accentColor }}>
          Image prompt
        </p>
        <p className="text-base leading-7" style={{ color: tokens.textColor }}>
          {slide.image_prompt ?? "No image prompt provided."}
        </p>
      </div>
    </div>
  );
}

function TitleSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="title slide" exportMode={exportMode}>
      <div className="flex h-full flex-col items-center justify-center text-center gap-8">
        <h2 className="max-w-4xl text-[clamp(2.4rem,4.5vw,4.6rem)] font-bold leading-[1.05] tracking-[-0.04em]" style={{ color: tokens.textColor, fontFamily: tokens.headingFontFamily }}>
          {slide.title}
        </h2>
        {slide.subtitle ? (
          <p className="mt-4 max-w-3xl text-[1.05rem] leading-8" style={{ color: tokens.mutedTextColor, fontFamily: tokens.bodyFontFamily }}>
            {slide.subtitle}
          </p>
        ) : null}
        {slide.notes ? (
          <p className="mt-5 max-w-2xl text-sm leading-6" style={{ color: tokens.mutedTextColor, fontFamily: tokens.bodyFontFamily }}>
            {slide.notes}
          </p>
        ) : null}
      </div>
    </SlideShell>
  );
}

function BulletsSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="bullet slide" exportMode={exportMode}>
      <div className="flex h-full flex-col justify-start gap-14">
        <h3 className="max-w-2xl text-[clamp(1.9rem,2.8vw,3.1rem)] font-bold leading-[1.12] tracking-[-0.03em]" style={{ color: tokens.textColor, fontFamily: tokens.headingFontFamily }}>
          {slide.title}
        </h3>
        <ul className="grid gap-4" style={{ color: tokens.textColor }}>
          {(slide.bullets ?? []).map((bullet) => (
            <li key={bullet} className="flex gap-4 rounded-[22px] border p-5 text-[1.05rem] leading-[1.65]" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}d9` }}>
              <span className="mt-2 h-2.5 w-2.5 rounded-full flex-none" style={{ backgroundColor: tokens.accentColor }} />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
        {slide.notes ? (
          <p className="text-sm leading-6" style={{ color: tokens.mutedTextColor }}>
            {slide.notes}
          </p>
        ) : null}
      </div>
    </SlideShell>
  );
}

function ImageBulletsSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="content + image" exportMode={exportMode}>
      <div className="grid h-full gap-10 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="flex flex-col justify-start gap-8">
          <h3 className="max-w-3xl text-[clamp(1.7rem,2.6vw,2.8rem)] font-bold leading-tight tracking-[-0.03em]" style={{ color: tokens.textColor, fontFamily: tokens.headingFontFamily }}>
            {slide.title}
          </h3>
          <ul className="grid gap-3">
            {(slide.bullets ?? []).map((bullet) => (
              <li key={bullet} className="rounded-[20px] border px-4 py-4 text-[0.98rem] leading-7" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}e6`, color: tokens.textColor }}>
                {bullet}
              </li>
            ))}
          </ul>
          {slide.notes ? (
            <p className="text-sm leading-6" style={{ color: tokens.mutedTextColor }}>
              {slide.notes}
            </p>
          ) : null}
        </div>
        <SlideImage slide={slide} presentation={presentation} tokens={tokens} exportMode={exportMode} />
      </div>
    </SlideShell>
  );
}

function HeroImageSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="hero image" exportMode={exportMode}>
      <div className="grid h-full gap-10 lg:grid-cols-[1fr_1.1fr]">
        <div className="flex flex-col justify-center gap-7">
          <h3 className="max-w-2xl text-[clamp(1.9rem,3.2vw,3.6rem)] font-bold leading-[1.08] tracking-[-0.04em]" style={{ color: tokens.textColor, fontFamily: tokens.headingFontFamily }}>
            {slide.title}
          </h3>
          {slide.subtitle ? (
            <p className="max-w-xl text-[1.03rem] leading-8" style={{ color: tokens.mutedTextColor, fontFamily: tokens.bodyFontFamily }}>
              {slide.subtitle}
            </p>
          ) : null}
          {slide.notes ? (
            <p className="max-w-xl text-sm leading-6" style={{ color: tokens.mutedTextColor, fontFamily: tokens.bodyFontFamily }}>
              {slide.notes}
            </p>
          ) : null}
        </div>
        <SlideImage slide={slide} presentation={presentation} tokens={tokens} exportMode={exportMode} />
      </div>
    </SlideShell>
  );
}

function ComparisonSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="comparison" exportMode={exportMode}>
      <div className="flex h-full flex-col gap-10">
        <h3 className="max-w-3xl text-[clamp(1.8rem,3vw,3.2rem)] font-bold leading-tight tracking-[-0.03em]" style={{ color: tokens.textColor, fontFamily: tokens.headingFontFamily }}>
          {slide.title}
        </h3>
        {slide.notes ? (
          <p className="mt-3 max-w-3xl text-sm leading-6" style={{ color: tokens.mutedTextColor, fontFamily: tokens.bodyFontFamily }}>
            {slide.notes}
          </p>
        ) : null}
        <div className="grid flex-1 gap-4 lg:grid-cols-2">
          <section className="rounded-[24px] border p-5" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}e8` }}>
            <p className="text-sm font-semibold uppercase tracking-[0.22em]" style={{ color: tokens.accentColor, fontFamily: tokens.headingFontFamily }}>
              {slide.left_title}
            </p>
            <ul className="mt-4 grid gap-3">
              {(slide.left_bullets ?? []).map((bullet) => (
                <li key={bullet} className="rounded-[18px] border px-4 py-3 text-sm leading-6" style={{ borderColor: tokens.borderColor, color: tokens.textColor }}>
                  {bullet}
                </li>
              ))}
            </ul>
          </section>
          <section className="rounded-[24px] border p-5" style={{ borderColor: tokens.borderColor, background: `linear-gradient(180deg, ${tokens.accentSoftColor}22, ${tokens.surface})` }}>
            <p className="text-sm font-semibold uppercase tracking-[0.22em]" style={{ color: tokens.accentColor, fontFamily: tokens.headingFontFamily }}>
              {slide.right_title}
            </p>
            <ul className="mt-4 grid gap-3">
              {(slide.right_bullets ?? []).map((bullet) => (
                <li key={bullet} className="rounded-[18px] border px-4 py-3 text-sm leading-6" style={{ borderColor: tokens.borderColor, color: tokens.textColor }}>
                  {bullet}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </SlideShell>
  );
}

function TimelineSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="timeline" exportMode={exportMode}>
      <div className="flex h-full flex-col gap-12">
        <h3 className="max-w-3xl text-[clamp(1.8rem,3.2vw,3.2rem)] font-bold leading-tight tracking-[-0.03em]" style={{ color: tokens.textColor }}>
          {slide.title}
        </h3>
        <div className="grid gap-4">
          {(slide.timeline ?? []).map((step, index) => (
            <div key={`${step.label}-${index}`} className="grid gap-3 rounded-[22px] border p-4 lg:grid-cols-[140px_1fr]" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}eb` }}>
              <div className="text-sm font-semibold uppercase tracking-[0.22em]" style={{ color: tokens.accentColor }}>
                {step.label}
              </div>
              <div className="text-sm leading-6" style={{ color: tokens.textColor }}>
                {step.detail ?? ""}
              </div>
            </div>
          ))}
        </div>
      </div>
    </SlideShell>
  );
}

function StatisticsSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="statistics" exportMode={exportMode}>
      <div className="flex h-full flex-col gap-10">
        <h3 className="max-w-3xl text-[clamp(1.8rem,3vw,3.2rem)] font-bold leading-tight tracking-[-0.03em]" style={{ color: tokens.textColor }}>
          {slide.title}
        </h3>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(slide.statistics ?? []).map((stat) => (
            <article key={stat.label} className="rounded-[22px] border p-5" style={{ borderColor: tokens.borderColor, background: `linear-gradient(180deg, ${tokens.surface}, ${tokens.backgroundAlt})` }}>
              <p className="text-4xl font-semibold tracking-[-0.05em]" style={{ color: tokens.accentColor }}>
                {stat.value}
              </p>
              <p className="mt-3 text-sm font-semibold uppercase tracking-[0.2em]" style={{ color: tokens.textColor }}>
                {stat.label}
              </p>
              {stat.detail ? (
                <p className="mt-2 text-sm leading-6" style={{ color: tokens.mutedTextColor }}>
                  {stat.detail}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </div>
    </SlideShell>
  );
}

function QuoteSlideRenderer({ slide, presentation, exportMode }: SlideRendererProps) {
  const tokens = resolveThemeTokens(presentation.theme);
  return (
    <SlideShell tokens={tokens} accentLabel="quote" exportMode={exportMode}>
      <div className="flex h-full flex-col justify-center gap-10 text-center">
        <blockquote className="mx-auto max-w-4xl">
          <p className="text-[clamp(1.8rem,3.5vw,4rem)] font-bold leading-[1.2] tracking-[-0.04em]" style={{ color: tokens.textColor }}>
            {slide.quote}
          </p>
          {slide.attribution ? (
            <footer className="mt-4 text-lg leading-7" style={{ color: tokens.mutedTextColor }}>
              {slide.attribution}
            </footer>
          ) : null}
        </blockquote>
        {slide.notes ? (
          <p className="mx-auto max-w-2xl text-sm leading-6" style={{ color: tokens.mutedTextColor }}>
            {slide.notes}
          </p>
        ) : null}
      </div>
    </SlideShell>
  );
}

export const slideRegistry: Record<SlideType, (props: SlideRendererProps) => ReactElement> = {
  title_slide: TitleSlideRenderer,
  title_bullets: BulletsSlideRenderer,
  title_bullets_image: ImageBulletsSlideRenderer,
  hero_image: HeroImageSlideRenderer,
  comparison: ComparisonSlideRenderer,
  timeline: TimelineSlideRenderer,
  statistics: StatisticsSlideRenderer,
  quote: QuoteSlideRenderer,
};

export function SlideDeck({
  presentation,
  layoutedPresentation,
  exportMode = false,
}: {
  presentation: Presentation;
  layoutedPresentation?: LayoutedPresentationDocument | null;
  exportMode?: boolean;
}) {
  return (
    <div className={exportMode ? "space-y-0" : "space-y-6"}>
      {presentation.slides.map((slide, index) => {
        const layoutedSlide = layoutedPresentation?.slides[index];
        const SlideComponent = slideRegistry[slide.type];
        return (
          <div key={slide.id} className={exportMode ? "break-after-page" : "space-y-3"}>
            {!exportMode ? (
              <div className="flex items-center justify-between gap-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                <span>Slide {index + 1}</span>
                <span>{slide.type.replace(/_/g, " ")}</span>
              </div>
            ) : null}
            <div className={exportMode ? "h-[720px] w-[1280px] max-w-full" : "aspect-[16/9] w-full"}>
              {layoutedSlide ? (
                <LayoutedSlideRenderer slide={slide} layoutedSlide={layoutedSlide} presentation={presentation} exportMode={exportMode} />
              ) : (
                <SlideComponent slide={slide} presentation={presentation} exportMode={exportMode} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
