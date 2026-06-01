"use client";

import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactElement, ReactNode } from "react";
import type { IconType } from "react-icons";
import {
  FiBarChart2,
  FiBookOpen,
  FiCheckCircle,
  FiChevronLeft,
  FiChevronRight,
  FiClock,
  FiCompass,
  FiEye,
  FiFilm,
  FiHeart,
  FiHome,
  FiImage,
  FiLayers,
  FiMap,
  FiMessageSquare,
  FiSearch,
  FiShield,
  FiStar,
  FiTarget,
  FiUser,
  FiZap,
} from "react-icons/fi";

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
const BULLET_ICONS: Record<string, IconType> = {
  bolt: FiZap,
  chart: FiBarChart2,
  book: FiBookOpen,
  clock: FiClock,
  eye: FiEye,
  film: FiFilm,
  heart: FiHeart,
  home: FiHome,
  idea: FiMessageSquare,
  map: FiMap,
  person: FiUser,
  route: FiCompass,
  search: FiSearch,
  shield: FiShield,
  star: FiStar,
  target: FiTarget,
};

function BulletIcon({ name, className = "h-4 w-4" }: { name?: string; className?: string }) {
  const Icon = BULLET_ICONS[name ?? "target"] ?? FiTarget;
  return <Icon className={className} aria-hidden="true" />;
}

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
      className={`relative h-full w-full overflow-hidden border shadow-[0_28px_80px_rgba(15,23,42,0.12)] ${exportMode ? "print:shadow-none" : ""}`}
      style={{
        ...themeStyle,
        padding: positioned ? 0 : `calc(2.5rem * ${tokens.spacingScale})`,
        background: `linear-gradient(145deg, ${tokens.background} 0%, ${tokens.backgroundAlt} 100%)`,
        borderColor: tokens.borderColor,
        borderRadius: tokens.panelStyle === "square" ? tokens.panelRadius : tokens.panelRadius + 14,
        boxShadow: tokens.shadow,
        color: tokens.textColor,
        fontFamily: tokens.bodyFontFamily,
      }}
    >
      <div
        className={`absolute ${tokens.accentPosition === "top" ? "inset-x-0 top-0 h-2" : "inset-y-0 left-0 w-2"}`}
        style={{ background: `linear-gradient(180deg, ${tokens.accentColor}, ${tokens.accentSoftColor})` }}
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

  if (element.kind === "panel") {
    return (
      <div
        style={{
          ...style,
          background: tokens.surface,
          border: `1px solid ${tokens.borderColor}`,
          borderRadius: tokens.panelStyle === "square" ? 0 : tokens.panelRadius,
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
          borderRadius: tokens.imageRadius,
          border: `1px solid ${tokens.borderColor}`,
          background: `linear-gradient(180deg, ${tokens.surface}, ${tokens.backgroundAlt})`,
          padding: tokens.imageFrameInset,
        }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={alt}
            className="h-full w-full"
            style={{ borderRadius: Math.max(0, tokens.imageRadius - tokens.imageFrameInset), objectFit: (content.fit as CSSProperties["objectFit"]) ?? tokens.imageFit }}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-5 text-center text-sm leading-6" style={{ color: tokens.textColor }}>
            <FiImage className="h-8 w-8" style={{ color: tokens.accentColor }} aria-hidden="true" />
            <span>{(content.prompt as string | undefined) ?? alt}</span>
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
    const isLine = tokens.bulletStyle === "lines";
    return (
      <div
        style={{
          ...style,
          display: "flex",
          alignItems: "flex-start",
          gap: 16,
          padding: "12px 14px",
          borderRadius: isLine ? 0 : Math.max(12, tokens.panelRadius - 4),
          border: isLine ? 0 : `1px solid ${tokens.borderColor}`,
          borderLeft: isLine ? `3px solid ${tokens.accentColor}` : undefined,
          background: isLine ? "transparent" : `${tokens.surface}d9`,
        }}
      >
        <span className="mt-0.5 flex h-7 w-7 flex-none items-center justify-center rounded-full" style={{ background: `${tokens.accentColor}24`, color: tokens.accentColor }}>
          <BulletIcon name={content.icon as string | undefined} />
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
        className={`h-full w-full ${exportMode ? "print:object-contain" : ""}`}
        style={{ border: `1px solid ${tokens.borderColor}`, borderRadius: tokens.imageRadius, objectFit: tokens.imageFit }}
      />
    );
  }

  return (
    <div
      className="flex h-full min-h-0 items-center justify-center p-5 text-center"
      style={{
        border: `1px dashed ${tokens.borderColor}`,
        borderRadius: tokens.imageRadius,
        background: `linear-gradient(180deg, ${tokens.surface}, ${tokens.backgroundAlt})`,
      }}
    >
      <div className="space-y-3">
        <FiImage className="mx-auto h-9 w-9" style={{ color: tokens.accentColor }} aria-hidden="true" />
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
        <FiZap className="h-10 w-10" style={{ color: tokens.accentColor }} aria-hidden="true" />
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
          {(slide.bullets ?? []).map((bullet, index) => (
            <li key={bullet} className="flex gap-4 rounded-[22px] border p-5 text-[1.05rem] leading-[1.65]" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}d9` }}>
              <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full" style={{ color: tokens.accentColor, background: `${tokens.accentColor}24` }}>
                <BulletIcon name={["target", "bolt", "idea", "chart"][index % 4]} />
              </span>
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
            {(slide.bullets ?? []).map((bullet, index) => (
              <li key={bullet} className="flex gap-3 rounded-[20px] border px-4 py-4 text-[0.98rem] leading-7" style={{ borderColor: tokens.borderColor, backgroundColor: `${tokens.surface}e6`, color: tokens.textColor }}>
                <BulletIcon name={["target", "bolt", "idea", "chart"][index % 4]} className="mt-1 h-4 w-4 flex-none" />
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
          <FiClock className="mb-4 h-8 w-8" style={{ color: tokens.accentColor }} aria-hidden="true" />
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
          <FiBarChart2 className="mb-4 h-8 w-8" style={{ color: tokens.accentColor }} aria-hidden="true" />
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
        <FiMessageSquare className="mx-auto h-10 w-10" style={{ color: tokens.accentColor }} aria-hidden="true" />
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

function SlideViewport({ children, compact = false }: { children: ReactNode; compact?: boolean }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }
    const updateScale = () => setScale(viewport.clientWidth / 1280);
    updateScale();
    const observer = new ResizeObserver(updateScale);
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={viewportRef} className={`relative aspect-[16/9] w-full overflow-hidden ${compact ? "sharp-control" : "sharp-panel"}`}>
      <div className="absolute left-0 top-0 h-[720px] w-[1280px] origin-top-left" style={{ transform: `scale(${scale})` }}>
        {children}
      </div>
    </div>
  );
}

function RenderedSlide({
  presentation,
  slide,
  layoutedSlide,
  exportMode,
}: {
  presentation: Presentation;
  slide: PresentationSlide;
  layoutedSlide?: LayoutedSlide;
  exportMode?: boolean;
}) {
  const SlideComponent = slideRegistry[slide.type];
  return layoutedSlide ? (
    <LayoutedSlideRenderer slide={slide} layoutedSlide={layoutedSlide} presentation={presentation} exportMode={exportMode} />
  ) : (
    <SlideComponent slide={slide} presentation={presentation} exportMode={exportMode} />
  );
}

export function SlideDeck({
  presentation,
  layoutedPresentation,
  exportMode = false,
}: {
  presentation: Presentation;
  layoutedPresentation?: LayoutedPresentationDocument | null;
  exportMode?: boolean;
}) {
  const [activeSlide, setActiveSlide] = useState(0);
  const lastSlide = presentation.slides.length - 1;

  useEffect(() => setActiveSlide(0), [presentation]);

  useEffect(() => {
    if (exportMode) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        setActiveSlide((current) => Math.max(0, current - 1));
      }
      if (event.key === "ArrowRight") {
        setActiveSlide((current) => Math.min(lastSlide, current + 1));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [exportMode, lastSlide]);

  if (!exportMode) {
    const slide = presentation.slides[activeSlide];
    const layoutedSlide = layoutedPresentation?.slides[activeSlide];
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">
          <span className="inline-flex items-center gap-2">
            <FiLayers className="h-4 w-4 text-white" aria-hidden="true" />
            Slide {activeSlide + 1} / {presentation.slides.length}
          </span>
          <span>{slide.type.replace(/_/g, " ")}</span>
        </div>
        <div key={slide.id} className="slide-enter sharp-panel overflow-hidden border border-white/10 bg-black shadow-[0_24px_80px_rgba(0,0,0,0.48)]">
          <SlideViewport>
            <RenderedSlide presentation={presentation} slide={slide} layoutedSlide={layoutedSlide} />
          </SlideViewport>
        </div>
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            disabled={activeSlide === 0}
            onClick={() => setActiveSlide((current) => Math.max(0, current - 1))}
            className="button-press interactive-outline sharp-control inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white [--control-bg:#101012] hover:[--control-bg:#18181b] disabled:cursor-not-allowed disabled:opacity-30"
          >
            <FiChevronLeft className="h-4 w-4" aria-hidden="true" />
            Previous
          </button>
          <div className="flex gap-1.5">
            {presentation.slides.map((item, index) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveSlide(index)}
                className={`button-press h-2 transition-all ${index === activeSlide ? "w-8 bg-white" : "w-2 bg-white/25 hover:bg-white/55"}`}
                aria-label={`Open slide ${index + 1}`}
              />
            ))}
          </div>
          <button
            type="button"
            disabled={activeSlide === lastSlide}
            onClick={() => setActiveSlide((current) => Math.min(lastSlide, current + 1))}
            className="button-press interactive-outline sharp-control inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white [--control-bg:#101012] hover:[--control-bg:#18181b] disabled:cursor-not-allowed disabled:opacity-30"
          >
            Next
            <FiChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {presentation.slides.map((item, index) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveSlide(index)}
              className={`button-press interactive-outline sharp-control w-32 flex-none p-1.5 text-left ${index === activeSlide ? "[--control-bg:#18181b]" : "[--control-bg:#0f0f11] hover:[--control-bg:#17171a]"}`}
            >
              <SlideViewport compact>
                <RenderedSlide presentation={presentation} slide={item} layoutedSlide={layoutedPresentation?.slides[index]} />
              </SlideViewport>
              <span className="mt-1.5 block truncate px-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-400">
                {index + 1}. {item.title ?? item.type}
              </span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {presentation.slides.map((slide, index) => {
        const layoutedSlide = layoutedPresentation?.slides[index];
        return (
          <div key={slide.id} className="break-after-page">
            <div className="h-[720px] w-[1280px] max-w-full">
              <RenderedSlide presentation={presentation} slide={slide} layoutedSlide={layoutedSlide} exportMode />
            </div>
          </div>
        );
      })}
    </div>
  );
}
