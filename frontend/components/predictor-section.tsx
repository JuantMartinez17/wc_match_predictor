"use client";

import { useState, useEffect } from "react";
import { RotateCcw, Calendar } from "lucide-react";
import type { Team, PredictResponse } from "@/types";
import TeamPicker from "./team-picker";
import PredictionResult from "./prediction-result";
import { fetchTeams, predictMatch } from "@/lib/api";

type Model = "dixon_coles" | "bivariate_poisson" | "poisson_simple";

export default function PredictorSection() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsError, setTeamsError] = useState(false);
  const [teamA, setTeamA] = useState<Team | null>(null);
  const [teamB, setTeamB] = useState<Team | null>(null);
  const [knockout, setKnockout] = useState(false);
  const [model, setModel] = useState<Model>("dixon_coles");
  const [matchDate, setMatchDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTeams()
      .then(setTeams)
      .catch(() => setTeamsError(true));
  }, []);

  async function handlePredict() {
    if (!teamA || !teamB) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await predictMatch({
        team_a: teamA.canonical,
        team_b: teamB.canonical,
        date: matchDate,
        knockout,
        model,
      });
      setResult(res);
      // Scroll result into view after render
      setTimeout(() => {
        document
          .getElementById("predictor-result")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setTeamA(null);
    setTeamB(null);
    setResult(null);
    setError(null);
  }

  return (
    <section id="predictor" className="border-t border-[#E8E6E1] bg-white">
      <div className="mx-auto max-w-7xl px-6 py-20 md:px-12">
        <div className="max-w-2xl">
          {/* Heading */}
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
            Predictor
          </p>
          <h2 className="text-[1.75rem] font-semibold leading-tight text-[#1B1B1B]">
            Predecí un partido
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#6B6B6B]">
            Elegí dos selecciones. El modelo calcula las probabilidades en base
            a datos históricos reales.
          </p>

          {teamsError && (
            <p className="mt-4 rounded-xl bg-[#FAEDEF] px-4 py-3 text-sm text-[#C95863]">
              No se pudo conectar al backend. Verificá que esté corriendo en{" "}
              <code className="font-mono">localhost:8000</code>.
            </p>
          )}

          {/* Team pickers */}
          <div className="mt-8 flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
                Equipo A
              </label>
              <TeamPicker
                teams={teams}
                value={teamA}
                onChange={setTeamA}
                placeholder="Selección A"
                disabled={teams.length === 0 && !teamsError}
              />
            </div>
            <span className="mb-4 shrink-0 text-sm font-semibold text-[#A8A29E]">
              vs
            </span>
            <div className="flex-1">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
                Equipo B
              </label>
              <TeamPicker
                teams={teams}
                value={teamB}
                onChange={setTeamB}
                placeholder="Selección B"
                disabled={teams.length === 0 && !teamsError}
              />
            </div>
          </div>

          {/* Options row */}
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {/* Date picker */}
            <label className="flex items-center gap-2 rounded-[10px] border border-[#E8E6E1] bg-white px-3 py-1.5 text-sm text-[#1B1B1B] focus-within:ring-2 focus-within:ring-[#183A70] focus-within:ring-offset-2">
              <Calendar size={14} className="shrink-0 text-[#A8A29E]" />
              <input
                type="date"
                value={matchDate}
                onChange={(e) => setMatchDate(e.target.value)}
                aria-label="Fecha del partido"
                className="bg-transparent text-sm text-[#1B1B1B] outline-none"
              />
            </label>

            {/* Knockout toggle */}
            <label className="flex cursor-pointer items-center gap-2.5">
              <button
                type="button"
                role="switch"
                aria-checked={knockout}
                onClick={() => setKnockout((v) => !v)}
                className={`relative h-5 w-9 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2 ${
                  knockout ? "bg-[#183A70]" : "bg-[#E8E6E1]"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-[left] duration-150 ${
                    knockout ? "left-[18px]" : "left-0.5"
                  }`}
                />
              </button>
              <span className="text-sm text-[#6B6B6B]">Eliminatoria</span>
            </label>

            {/* Model selector */}
            <select
              value={model}
              onChange={(e) => setModel(e.target.value as Model)}
              className="rounded-[10px] border border-[#E8E6E1] bg-white px-3 py-1.5 text-sm text-[#1B1B1B] outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
            >
              <option value="dixon_coles">Dixon-Coles</option>
              <option value="bivariate_poisson">Poisson bivariado</option>
              <option value="poisson_simple">Poisson simple</option>
            </select>
          </div>

          {/* Actions */}
          <div className="mt-6 flex items-center gap-3">
            <button
              type="button"
              onClick={handlePredict}
              disabled={!teamA || !teamB || loading}
              className="flex items-center gap-2 rounded-xl bg-[#183A70] px-7 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-[#224989] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Calculando...
                </>
              ) : (
                "Predecir"
              )}
            </button>

            {(result || error) && (
              <button
                type="button"
                onClick={reset}
                className="flex items-center gap-1.5 rounded-xl border border-[#E8E6E1] px-4 py-3.5 text-sm text-[#6B6B6B] transition-colors hover:bg-[#F8F7F5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
              >
                <RotateCcw size={13} />
                Limpiar
              </button>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-xl bg-[#FAEDEF] px-4 py-3 text-sm text-[#C95863]">
              {error}
            </p>
          )}
        </div>

        {/* Result */}
        {result && (
          <div id="predictor-result" className="mt-2 max-w-2xl scroll-mt-20">
            <div className="rounded-2xl border border-[#E8E6E1] bg-white p-8">
              <PredictionResult result={result} />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
