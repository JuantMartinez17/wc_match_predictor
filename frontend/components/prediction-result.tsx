import type { PredictResponse } from "@/types";
import FlagImage from "./flag-image";

interface Props {
  result: PredictResponse;
  compact?: boolean;
}

export default function PredictionResult({ result, compact = false }: Props) {
  const {
    team_a_es,
    team_b_es,
    flag_a,
    flag_b,
    p_a,
    p_draw,
    p_b,
    xg_a,
    xg_b,
    top_scorelines,
    narrative,
    venue_label,
    is_knockout,
    p_advance_a,
    p_advance_b,
  } = result;

  const pAp = Math.round(p_a * 100);
  const pDp = Math.round(p_draw * 100);
  const pBp = Math.round(p_b * 100);

  // ── Compact variant (inside fixture cards) ──────────────────────────────────
  if (compact) {
    return (
      <div className="space-y-3">
        {/* Segmented bar */}
        <div>
          <div className="flex h-2 overflow-hidden rounded-full">
            <div style={{ width: `${pAp}%` }} className="bg-[#183A70]" />
            <div style={{ width: `${pDp}%` }} className="bg-[#C8C4BE]" />
            <div style={{ width: `${pBp}%` }} className="bg-[#7C2946]" />
          </div>
          <div className="mt-2 flex justify-between text-xs">
            <span>
              <span className="font-semibold text-[#183A70]">{pAp}%</span>
              <span className="ml-1 text-[#A8A29E]">local</span>
            </span>
            <span className="text-[#A8A29E]">Empate {pDp}%</span>
            <span>
              <span className="font-semibold text-[#7C2946]">{pBp}%</span>
              <span className="ml-1 text-[#A8A29E]">visitante</span>
            </span>
          </div>
        </div>

        {/* xG row */}
        <div className="flex items-center justify-between rounded-lg bg-[#F8F7F5] px-4 py-2">
          <span className="font-semibold text-sm text-[#1B1B1B]">
            {xg_a.toFixed(1)} xG
          </span>
          <span className="text-xs text-[#A8A29E]">goles esperados</span>
          <span className="font-semibold text-sm text-[#1B1B1B]">
            {xg_b.toFixed(1)} xG
          </span>
        </div>

        {/* Top scoreline */}
        {top_scorelines[0] && (
          <p className="text-center text-xs text-[#6B6B6B]">
            Marcador más probable:{" "}
            <span className="font-semibold text-[#1B1B1B]">
              {top_scorelines[0].score_a}–{top_scorelines[0].score_b}
            </span>{" "}
            ({Math.round(top_scorelines[0].probability * 100)}%)
          </p>
        )}
      </div>
    );
  }

  // ── Winner callout derivation ──────────────────────────────────────────────
  const drawMostLikely = p_draw >= p_a && p_draw >= p_b;
  const favorsA = p_a >= p_b;
  const winnerName = drawMostLikely ? "Empate" : favorsA ? team_a_es : team_b_es;
  const winnerProb = drawMostLikely ? p_draw : Math.max(p_a, p_b);
  const confidence =
    winnerProb >= 0.6 ? "Alta" : winnerProb >= 0.45 ? "Media" : "Baja";

  // ── Full variant (predictor section) ───────────────────────────────────────
  return (
    <div className="space-y-6 rounded-2xl border border-[#E8E6E1] bg-white p-8">
      {/* Teams header */}
      <div className="flex items-center gap-4">
        <div className="flex flex-1 flex-col items-center gap-2">
          <FlagImage iso2={flag_a} name={team_a_es} size="lg" className="shadow-sm" />
          <span className="text-center text-lg font-semibold text-[#1B1B1B]">
            {team_a_es}
          </span>
        </div>
        <span className="text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
          vs
        </span>
        <div className="flex flex-1 flex-col items-center gap-2">
          <FlagImage iso2={flag_b} name={team_b_es} size="lg" className="shadow-sm" />
          <span className="text-center text-lg font-semibold text-[#1B1B1B]">
            {team_b_es}
          </span>
        </div>
      </div>

      {/* Probability bars */}
      <div>
        <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
          Probabilidades a 90&apos;
        </p>
        <div className="space-y-4">
          {(
            [
              { label: team_a_es, value: p_a, color: "#183A70" },
              { label: "Empate", value: p_draw, color: "#A8A29E" },
              { label: team_b_es, value: p_b, color: "#7C2946" },
            ] as const
          ).map(({ label, value, color }) => (
            <div key={label}>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className="font-medium text-[#1B1B1B]">{label}</span>
                <span className="font-semibold" style={{ color }}>
                  {Math.round(value * 100)}%
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#E8E6E1]">
                <div
                  className="h-2.5 rounded-full"
                  style={{
                    width: `${Math.round(value * 100)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Expected goals */}
      <div className="flex items-center justify-between rounded-xl bg-[#F8F7F5] px-8 py-5">
        <div className="text-center">
          <p className="mb-1 text-xs uppercase tracking-widest text-[#A8A29E]">
            xG {team_a_es}
          </p>
          <p className="font-mono text-3xl font-bold text-[#1B1B1B]">
            {xg_a.toFixed(1)}
          </p>
        </div>
        <span className="text-2xl font-light text-[#E8E6E1]">—</span>
        <div className="text-center">
          <p className="mb-1 text-xs uppercase tracking-widest text-[#A8A29E]">
            xG {team_b_es}
          </p>
          <p className="font-mono text-3xl font-bold text-[#1B1B1B]">
            {xg_b.toFixed(1)}
          </p>
        </div>
      </div>

      {/* Top scorelines */}
      {top_scorelines.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
            Marcadores más probables
          </p>
          <div className="grid grid-cols-4 gap-2">
            {top_scorelines.slice(0, 8).map((s, i) => (
              <div
                key={i}
                className="flex flex-col items-center rounded-lg border border-[#E8E6E1] px-2 py-3"
              >
                <span className="text-base font-bold text-[#1B1B1B]">
                  {s.score_a}–{s.score_b}
                </span>
                <span className="mt-0.5 text-xs text-[#A8A29E]">
                  {Math.round(s.probability * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Knockout advance probabilities */}
      {is_knockout && p_advance_a != null && p_advance_b != null && (
        <div className="flex gap-3">
          <div className="flex-1 rounded-xl bg-[#EEF2F9] p-4 text-center">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[#183A70]">
              Avanza {team_a_es}
            </p>
            <p className="text-2xl font-bold text-[#183A70]">
              {Math.round(p_advance_a * 100)}%
            </p>
          </div>
          <div className="flex-1 rounded-xl bg-[#F5EEF1] p-4 text-center">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[#7C2946]">
              Avanza {team_b_es}
            </p>
            <p className="text-2xl font-bold text-[#7C2946]">
              {Math.round(p_advance_b * 100)}%
            </p>
          </div>
        </div>
      )}

      {/* Narrative */}
      <div className="rounded-xl bg-[#F8F7F5] px-5 py-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#A8A29E]">
          Análisis
        </p>
        <p className="text-sm leading-7 text-[#6B6B6B]">{narrative}</p>
      </div>

      {/* Winner callout */}
      <div className="rounded-xl bg-[#F7F2E6] px-6 py-5">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#A8894A]">
          Resultado más probable
        </p>
        <p className="mt-1.5 text-2xl font-bold text-[#A8894A]">{winnerName}</p>
        <p className="mt-1 text-sm text-[#6B6B6B]">Confianza: {confidence}</p>
      </div>

      {/* Venue */}
      <p className="text-xs text-[#A8A29E]">{venue_label}</p>
    </div>
  );
}
