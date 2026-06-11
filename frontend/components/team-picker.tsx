"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import type { Team } from "@/types";
import FlagImage from "./flag-image";

interface Props {
  teams: Team[];
  value: Team | null;
  onChange: (team: Team | null) => void;
  placeholder?: string;
  disabled?: boolean;
}

export default function TeamPicker({
  teams,
  value,
  onChange,
  placeholder = "Elegir selección",
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const filtered = query.trim()
    ? teams.filter((t) =>
        t.name_es.toLowerCase().includes(query.toLowerCase())
      )
    : teams;

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
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-[10px] border border-[#E8E6E1] bg-white px-4 py-3.5 text-left text-sm transition hover:border-[#183A70]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {value ? (
          <>
            <FlagImage iso2={value.flag} name={value.name_es} size="xs" />
            <span className="font-medium text-[#1B1B1B]">{value.name_es}</span>
          </>
        ) : (
          <span className="text-[#A8A29E]">{placeholder}</span>
        )}
        <ChevronDown
          size={14}
          className={`ml-auto shrink-0 text-[#A8A29E] transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-[10px] border border-[#E8E6E1] bg-white shadow-lg">
          <div className="border-b border-[#E8E6E1] px-3 py-2.5">
            <div className="flex items-center gap-2">
              <Search size={13} className="shrink-0 text-[#A8A29E]" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar..."
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-[#A8A29E]"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="text-[#A8A29E] hover:text-[#1B1B1B]"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-4 py-3 text-sm text-[#A8A29E]">
                Sin resultados
              </li>
            ) : (
              filtered.map((team) => (
                <li key={team.canonical}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(team);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-[#F8F7F5] ${
                      value?.canonical === team.canonical
                        ? "bg-[#EEF2F9] font-medium"
                        : ""
                    }`}
                  >
                    <FlagImage iso2={team.flag} name={team.name_es} size="xs" />
                    {team.name_es}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
