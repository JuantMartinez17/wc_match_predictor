"use client";

import { useState, useEffect } from "react";
import type { FixtureMatch, PredictResponse } from "@/types";
import { fetchFixture, predictMatch } from "@/lib/api";
import PredictionResult from "./prediction-result";
import FlagImage from "./flag-image";

// ── Helpers ────────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, string> = {
  "en juego": "text-emerald-700 bg-emerald-50",
  descanso: "text-amber-700 bg-amber-50",
  finalizado: "text-[#6B6B6B] bg-[#F8F7F5]",
  postergado: "text-[#C95863] bg-[#FAEDEF]",
  cancelado: "text-[#C95863] bg-[#FAEDEF]",
  suspendido: "text-[#C95863] bg-[#FAEDEF]",
  programado: "text-[#6B6B6B] bg-[#F8F7F5]",
};

const STATUS_LABEL: Record<string, string> = {
  "en juego": "En juego",
  descanso: "Descanso",
  finalizado: "Finalizado",
  postergado: "Postergado",
  cancelado: "Cancelado",
  suspendido: "Suspendido",
  programado: "Programado",
};

function formatDay(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

// ── Match card ─────────────────────────────────────────────────────────────

function MatchCard({ match }: { match: FixtureMatch }) {
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const statusStyle =
    STATUS_STYLE[match.status] ?? "text-[#6B6B6B] bg-[#F8F7F5]";
  const statusLabel = STATUS_LABEL[match.status] ?? match.status;
  const hasScore =
    match.score_a !== "" &&
    match.score_b !== "" &&
    match.score_a !== "None" &&
    match.score_b !== "None";

  async function handleToggle() {
    if (prediction) {
      setOpen((v) => !v);
      return;
    }
    setLoading(true);
    try {
      const res = await predictMatch({
        team_a: match.team_a,
        team_b: match.team_b,
      });
      setPrediction(res);
      setOpen(true);
    } catch {
      // fail silently — button stays available to retry
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[#E8E6E1] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)]">
      <div className="p-6">
        {/* Meta row */}
        <div className="mb-4 flex items-center justify-between">
          <span className="text-xs text-[#A8A29E]">
            {match.time_utc} UTC
          </span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}
          >
            {statusLabel}
          </span>
        </div>

        {/* Teams */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-1 flex-col items-center gap-2">
            <FlagImage iso2={match.flag_a} name={match.team_a_es} size="md" />
            <span className="text-center text-sm font-semibold leading-tight text-[#1B1B1B]">
              {match.team_a_es}
            </span>
          </div>

          <div className="flex flex-col items-center gap-0.5">
            {hasScore ? (
              <span className="text-2xl font-bold text-[#1B1B1B]">
                {match.score_a} – {match.score_b}
              </span>
            ) : (
              <span className="text-sm font-semibold text-[#C8C4BE]">vs</span>
            )}
          </div>

          <div className="flex flex-1 flex-col items-center gap-2">
            <FlagImage iso2={match.flag_b} name={match.team_b_es} size="md" />
            <span className="text-center text-sm font-semibold leading-tight text-[#1B1B1B]">
              {match.team_b_es}
            </span>
          </div>
        </div>

        {/* Round */}
        {match.round && (
          <p className="mt-3 text-center text-xs text-[#A8A29E]">
            {match.round}
          </p>
        )}
      </div>

      {/* Predict button */}
      <div className="border-t border-[#E8E6E1] px-6 py-3">
        <button
          type="button"
          onClick={handleToggle}
          disabled={loading}
          className="w-full rounded-sm text-center text-xs font-semibold uppercase tracking-widest text-[#183A70] transition-colors hover:text-[#224989] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2 disabled:opacity-40"
        >
          {loading
            ? "Calculando..."
            : open
            ? "Ocultar predicción"
            : "Ver predicción"}
        </button>
      </div>

      {/* Inline prediction */}
      {open && prediction && (
        <div className="border-t border-[#E8E6E1] p-6">
          <PredictionResult result={prediction} compact />
        </div>
      )}
    </div>
  );
}

// ── Section ────────────────────────────────────────────────────────────────

export default function FixtureSection() {
  const [matches, setMatches] = useState<FixtureMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [daysAhead, setDaysAhead] = useState(7);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchFixture(daysAhead);
        if (!cancelled) setMatches(data);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Error al cargar fixture");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [daysAhead]);

  // Group matches by date
  const grouped = matches.reduce<Record<string, FixtureMatch[]>>((acc, m) => {
    if (!acc[m.date]) acc[m.date] = [];
    acc[m.date].push(m);
    return acc;
  }, {});
  const sortedDates = Object.keys(grouped).sort();

  return (
    <section id="fixture" className="mx-auto max-w-7xl px-6 py-20 md:px-12">
      {/* Heading */}
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
        Fixture
      </p>
      <h2 className="text-[1.75rem] font-semibold leading-tight text-[#1B1B1B]">
        Próximos partidos
      </h2>
      <p className="mt-2 text-sm leading-6 text-[#6B6B6B]">
        Hacé clic en &quot;Ver predicción&quot; para analizar cualquier partido.
      </p>

      {/* States */}
      {loading && (
        <div className="mt-12 flex justify-center">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-[#E8E6E1] border-t-[#183A70]" />
        </div>
      )}

      {error && (
        <p className="mt-8 rounded-xl bg-[#FAEDEF] px-4 py-3 text-sm text-[#C95863]">
          {error}
        </p>
      )}

      {!loading && !error && matches.length === 0 && (
        <p className="mt-8 text-sm text-[#A8A29E]">
          No hay partidos en el período seleccionado.
        </p>
      )}

      {/* Grouped by date */}
      {!loading && sortedDates.length > 0 && (
        <div className="mt-10 space-y-10">
          {sortedDates.map((date) => (
            <div key={date}>
              <h3 className="mb-4 text-sm font-semibold capitalize text-[#6B6B6B]">
                {formatDay(date)}
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {grouped[date].map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Load more */}
      {!loading && matches.length > 0 && daysAhead < 30 && (
        <div className="mt-10 flex justify-center">
          <button
            type="button"
            onClick={() => setDaysAhead((v) => Math.min(v + 7, 30))}
            className="rounded-xl border border-[#E8E6E1] bg-white px-7 py-3 text-sm font-semibold text-[#6B6B6B] transition-colors hover:bg-[#F8F7F5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
          >
            Ver más partidos
          </button>
        </div>
      )}
    </section>
  );
}
