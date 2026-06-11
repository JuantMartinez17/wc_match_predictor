"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export type Model = "dixon_coles" | "bivariate_poisson" | "poisson_simple";

interface ModelOption {
  value: Model;
  label: string;
  description: string;
  recommended?: boolean;
}

export const MODELS: ModelOption[] = [
  {
    value: "dixon_coles",
    label: "Dixon-Coles",
    description:
      "El más preciso. Ajusta los partidos de pocos goles y da más peso a los resultados recientes.",
    recommended: true,
  },
  {
    value: "bivariate_poisson",
    label: "Poisson bivariado",
    description:
      "Estima los goles de ambos equipos teniendo en cuenta la correlación entre sí.",
  },
  {
    value: "poisson_simple",
    label: "Poisson simple",
    description:
      "Modelo base. Estima los goles de cada equipo de forma independiente.",
  },
];

interface Props {
  value: Model;
  onChange: (model: Model) => void;
}

export default function ModelPicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = MODELS.find((m) => m.value === value) ?? MODELS[0];

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  return (
    <div ref={ref} className="relative w-full">
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-[10px] border border-[#E8E6E1] bg-white px-3 py-1.5 text-left text-sm transition hover:border-[#183A70]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
      >
        <span className="shrink-0 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
          Modelo
        </span>
        <span className="font-medium text-[#1B1B1B]">{selected.label}</span>
        <ChevronDown
          size={14}
          className={`ml-auto shrink-0 text-[#A8A29E] transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-20 mt-1 w-full min-w-[18rem] overflow-hidden rounded-[10px] border border-[#E8E6E1] bg-white shadow-lg">
          <ul className="py-1">
            {MODELS.map((m) => {
              const active = m.value === value;
              return (
                <li key={m.value}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(m.value);
                      setOpen(false);
                    }}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[#F8F7F5] ${
                      active ? "bg-[#EEF2F9]" : ""
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[#1B1B1B]">
                          {m.label}
                        </span>
                        {m.recommended && (
                          <span className="rounded-full bg-[#EEF2F9] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#183A70]">
                            Recomendado
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs leading-5 text-[#6B6B6B]">
                        {m.description}
                      </p>
                    </div>
                    {active && (
                      <Check
                        size={15}
                        className="mt-0.5 shrink-0 text-[#183A70]"
                      />
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
