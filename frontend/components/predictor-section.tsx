"use client";

import { useState, useEffect } from "react";
import { RotateCcw, Calendar } from "lucide-react";
import type { Team, PredictResponse } from "@/types";
import TeamPicker from "./team-picker";
import ModelPicker, { type Model } from "./model-picker";
import PredictionResult from "./prediction-result";
import { fetchTeams, predictMatch } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export default function PredictorSection() {
  const { t } = useLanguage();
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
        team_a_id: teamA.id,
        team_b_id: teamB.id,
        date: matchDate,
        knockout,
        model,
      });
      setResult(res);
      setTimeout(() => {
        document
          .getElementById("predictor-result")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t.predictor.errorPredict
      );
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
    <section id="predictor" className="border-t border-line bg-surface">
      <div className="mx-auto max-w-7xl px-6 py-20 md:px-12">
        <div className="mx-auto max-w-2xl">
          <div className="text-center">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
              {t.predictor.sectionLabel}
            </p>
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink md:text-4xl">
              {t.predictor.heading}
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              {t.predictor.description}
            </p>
          </div>

          {teamsError && (
            <p className="mt-4 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
              {t.predictor.errorLoad}
            </p>
          )}

          <div className="mt-8 flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-ink-subtle">
                {t.predictor.teamALabel}
              </label>
              <TeamPicker
                teams={teams}
                value={teamA}
                onChange={setTeamA}
                placeholder={t.predictor.placeholderA}
                disabled={teams.length === 0 && !teamsError}
              />
            </div>
            <span className="mb-4 shrink-0 text-sm font-semibold text-ink-subtle">
              {t.fixture.vs}
            </span>
            <div className="flex-1">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-ink-subtle">
                {t.predictor.teamBLabel}
              </label>
              <TeamPicker
                teams={teams}
                value={teamB}
                onChange={setTeamB}
                placeholder={t.predictor.placeholderB}
                disabled={teams.length === 0 && !teamsError}
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
            <label className="flex items-center gap-2 rounded-[10px] border border-line bg-surface px-3 py-1.5 text-sm text-ink focus-within:ring-2 focus-within:ring-brand focus-within:ring-offset-2">
              <Calendar size={14} className="shrink-0 text-ink-subtle" />
              <input
                type="date"
                value={matchDate}
                onChange={(e) => setMatchDate(e.target.value)}
                aria-label={t.predictor.dateAriaLabel}
                className="bg-transparent text-sm text-ink outline-none"
              />
            </label>

            <label className="flex cursor-pointer items-center gap-2.5">
              <button
                type="button"
                role="switch"
                aria-checked={knockout}
                onClick={() => setKnockout((v) => !v)}
                className={`relative h-5 w-9 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 ${
                  knockout ? "bg-brand" : "bg-line"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-[left] duration-150 ${
                    knockout ? "left-[18px]" : "left-0.5"
                  }`}
                />
              </button>
              <span className="text-sm text-ink-muted">{t.predictor.knockout}</span>
            </label>

            <div className="w-full sm:w-auto">
              <ModelPicker value={model} onChange={setModel} />
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              type="button"
              onClick={handlePredict}
              disabled={!teamA || !teamB || loading}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand px-7 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  {t.predictor.calculating}
                </>
              ) : (
                t.predictor.predict
              )}
            </button>

            {(result || error) && (
              <button
                type="button"
                onClick={reset}
                className="flex items-center gap-1.5 rounded-xl border border-line px-4 py-3.5 text-sm text-ink-muted transition-colors hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
              >
                <RotateCcw size={13} />
                {t.predictor.clear}
              </button>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
              {error}
            </p>
          )}
        </div>

        {result && (
          <div id="predictor-result" className="mx-auto mt-2 max-w-2xl scroll-mt-20">
            <div className="rounded-2xl border border-line bg-surface p-8">
              <PredictionResult result={result} />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
