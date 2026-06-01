import type { ThemeName } from "@/lib/api";
import { TEMPLATE_OPTIONS } from "@/lib/theme";

interface TemplateSelectorProps {
  disabled?: boolean;
  value: ThemeName;
  onChange: (value: ThemeName) => void;
}

export function TemplateSelector({ disabled, value, onChange }: TemplateSelectorProps) {
  return (
    <fieldset className="mb-5">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <legend className="text-sm font-medium text-slate-700">Template</legend>
        <span className="text-xs text-slate-500">Hardcoded and export-safe</span>
      </div>
      <div className="grid max-h-[660px] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
        {TEMPLATE_OPTIONS.map((template) => {
          const active = template.name === value;
          return (
            <button
              key={template.name}
              type="button"
              disabled={disabled}
              onClick={() => onChange(template.name)}
              aria-pressed={active}
              className={`group rounded-2xl border p-3 text-left transition ${
                active
                  ? "border-spark bg-teal-50 shadow-sm ring-2 ring-spark/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
              } disabled:cursor-not-allowed disabled:opacity-60`}
            >
              <div
                className="relative overflow-hidden rounded-xl border px-4 py-4"
                style={{
                  borderColor: template.borderColor,
                  background: `linear-gradient(145deg, ${template.background}, ${template.backgroundAlt})`,
                }}
              >
                <span
                  className={`absolute ${template.accentPosition === "top" ? "inset-x-0 top-0 h-1.5" : "inset-y-0 left-0 w-1.5"}`}
                  style={{ background: template.accentColor }}
                />
                <div className="relative flex min-h-[6.5rem] flex-col justify-between gap-3 pt-1">
                  <div>
                    <p
                      className="text-[0.68rem] font-semibold uppercase tracking-[0.22em]"
                      style={{ color: template.accentColor, fontFamily: template.bodyFontFamily }}
                    >
                      Theme preview
                    </p>
                    <p
                      className="mt-2 text-[1rem] font-semibold leading-tight"
                      style={{ color: template.textColor, fontFamily: template.headingFontFamily }}
                    >
                      {template.displayName}
                    </p>
                    <p
                      className="mt-1 text-[0.78rem] leading-5"
                      style={{ color: template.mutedTextColor, fontFamily: template.bodyFontFamily }}
                    >
                      {template.description}
                    </p>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span
                      className="inline-flex rounded-full border px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.18em]"
                      style={{
                        borderColor: template.borderColor,
                        color: template.textColor,
                        background: template.surface,
                        fontFamily: template.headingFontFamily,
                      }}
                    >
                      Aa
                    </span>
                    <span
                      className="max-w-[68%] text-right text-[0.68rem] leading-4"
                      style={{ color: template.textColor, fontFamily: template.bodyFontFamily }}
                    >
                      {template.useCases[0]}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-3 flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ink">{template.displayName}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{template.description}</p>
                </div>
                <span
                  className={`mt-0.5 h-4 w-4 flex-none rounded-full border ${
                    active ? "border-spark bg-spark" : "border-slate-300 bg-white"
                  }`}
                />
              </div>
              <p className="mt-2 text-[11px] leading-4 text-slate-500">
                Best for: {template.useCases.slice(0, 3).join(", ")}
              </p>
              <div className="mt-3 flex gap-1.5">
                {template.palette.map((color) => (
                  <span
                    key={color}
                    className="h-3 w-3 rounded-full border border-black/10"
                    style={{ background: color }}
                  />
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
