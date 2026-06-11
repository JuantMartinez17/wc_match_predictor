"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export type Model = "dixon_coles" | "bivariate_poisson" | "poisson_simple";

const MODEL_KEYS: { value: Model; recommended?: boolean }[] = [
  { value: "dixon_coles", recommended: true },
  { value: "bivariate_poisson" },
  { value: "poisson_simple" },
];

interface Props {
  value: Model;
  onChange: (model: Model) => void;
}

export default function ModelPicker({ value, onChange }: Props) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const selectedLabel = t.modelPicker[value].label;

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-[10px] border border-line bg-surface px-3 py-1.5 text-left text-sm transition hover:border-brand/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
      >
        <span className="shrink-0 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.modelPicker.label}
        </span>
        <span className="font-medium text-ink">{selectedLabel}</span>
        <ChevronDown
          size={14}
          className={`ml-auto shrink-0 text-ink-subtle transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full min-w-[18rem] overflow-hidden rounded-[10px] border border-line bg-surface shadow-lg">
          <ul className="py-1">
            {MODEL_KEYS.map((m) => {
              const active = m.value === value;
              const model = t.modelPicker[m.value];
              return (
                <li key={m.value}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(m.value);
                      setOpen(false);
                    }}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-canvas ${
                      active ? "bg-brand-soft" : ""
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-ink">
                          {model.label}
                        </span>
                        {m.recommended && (
                          <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand">
                            {t.modelPicker.recommended}
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                        {model.description}
                      </p>
                    </div>
                    {active && (
                      <Check size={15} className="mt-0.5 shrink-0 text-brand" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
