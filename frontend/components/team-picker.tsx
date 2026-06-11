"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import type { Team } from "@/types";
import FlagImage from "./flag-image";
import { useLanguage } from "@/lib/i18n";

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
  placeholder,
  disabled,
}: Props) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const resolvedPlaceholder = placeholder ?? t.teamPicker.placeholder;

  const filtered = query.trim()
    ? teams.filter((team) =>
        team.name_es.toLowerCase().includes(query.toLowerCase())
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
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-[10px] border border-line bg-surface px-4 py-3.5 text-left text-sm transition hover:border-brand/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {value ? (
          <>
            <FlagImage iso2={value.flag} name={value.name_es} size="xs" />
            <span className="font-medium text-ink">{value.name_es}</span>
          </>
        ) : (
          <span className="text-ink-subtle">{resolvedPlaceholder}</span>
        )}
        <ChevronDown
          size={14}
          className={`ml-auto shrink-0 text-ink-subtle transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-[10px] border border-line bg-surface shadow-lg">
          <div className="border-b border-line px-3 py-2.5">
            <div className="flex items-center gap-2">
              <Search size={13} className="shrink-0 text-ink-subtle" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t.teamPicker.search}
                className="flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-subtle"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="text-ink-subtle hover:text-ink"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-4 py-3 text-sm text-ink-subtle">
                {t.teamPicker.noResults}
              </li>
            ) : (
              filtered.map((team) => (
                <li key={team.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(team);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-canvas ${
                      value?.id === team.id ? "bg-brand-soft font-medium" : ""
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
