"use client";

import type { PredictResponse, ScoreProbability } from "@/types";
import FlagImage from "./flag-image";
import { useLanguage } from "@/lib/i18n";

interface Props {
  result: PredictResponse;
}

const TEAM_A = "var(--result-a)";
const TEAM_B = "var(--result-b)";
const DRAW   = "var(--result-draw)";

function scoreWinnerColor(a: number, b: number): string {
  if (a === b) return DRAW;
  return a > b ? TEAM_A : TEAM_B;
}

function WinnerLegend({ teamA, teamB }: { teamA: string; teamB: string }) {
  const { t } = useLanguage();
  const items: [string, string][] = [
    [TEAM_A, teamA],
    [DRAW, t.result.draw],
    [TEAM_B, teamB],
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
      {items.map(([color, label]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function Scorelines({
  scorelines,
  teamA,
  teamB,
  dense = false,
}: {
  scorelines: ScoreProbability[];
  teamA: string;
  teamB: string;
  dense?: boolean;
}) {
  const { t } = useLanguage();
  if (scorelines.length === 0) return null;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.result.mostLikelyScores}
        </p>
        <WinnerLegend teamA={teamA} teamB={teamB} />
      </div>
      <div className="grid grid-cols-4 gap-2">
        {scorelines.slice(0, 8).map((s, i) => {
          const color = scoreWinnerColor(s.score_a, s.score_b);
          return (
            <div
              key={i}
              className={`flex flex-col items-center rounded-lg border border-line ${
                dense ? "px-1 py-2" : "px-2 py-3"
              }`}
              style={{ borderBottom: `2px solid ${color}` }}
            >
              <span
                className={`font-bold ${dense ? "text-sm" : "text-base"}`}
                style={{ color }}
              >
                {s.score_a}–{s.score_b}
              </span>
              <span className="mt-0.5 text-xs text-ink-subtle">
                {Math.round(s.probability * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FormationRow({
  flag,
  name,
  confirmed,
  desc,
}: {
  flag: string;
  name: string;
  confirmed: boolean;
  desc: string;
}) {
  const { t } = useLanguage();
  return (
    <div className="flex items-start gap-2.5">
      <FlagImage iso2={flag} name={name} size="xs" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium text-ink">{name}</span>
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6875rem] font-medium ${
              confirmed ? "bg-brand-soft text-brand" : "bg-canvas text-ink-muted"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                confirmed ? "bg-brand" : "bg-ink-subtle"
              }`}
            />
            {confirmed ? t.result.lineupConfirmed : t.result.lineupPending}
          </span>
        </div>
        {desc && <p className="mt-0.5 text-xs leading-5 text-ink-muted">{desc}</p>}
      </div>
    </div>
  );
}

export default function PredictionResult({ result }: Props) {
  const { t } = useLanguage();
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
    neutral,
    home_team_id,
    squad_desc_a,
    squad_desc_b,
    lineup_confirmed_a,
    lineup_confirmed_b,
    is_knockout,
    p_penalties,
    p_advance_a,
    p_advance_b,
  } = result;

  const drawMostLikely = p_draw >= p_a && p_draw >= p_b;
  const favorsA = p_a >= p_b;
  const winnerName = drawMostLikely ? t.result.draw : favorsA ? team_a_es : team_b_es;
  const winnerFlag = drawMostLikely ? null : favorsA ? flag_a : flag_b;
  const winnerHeadline = drawMostLikely
    ? t.result.draw
    : t.result.winsTeamHeadline(favorsA ? team_a_es : team_b_es);
  const winnerProb = drawMostLikely ? p_draw : Math.max(p_a, p_b);
  const confidence =
    winnerProb >= 0.6
      ? t.result.confidenceHigh
      : winnerProb >= 0.45
      ? t.result.confidenceMedium
      : t.result.confidenceLow;
  const topScore = top_scorelines[0];

  const isHome = !neutral && home_team_id != null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="flex flex-1 flex-col items-center gap-2">
          <FlagImage iso2={flag_a} name={team_a_es} size="lg" className="shadow-sm" />
          <span className="text-center text-lg font-semibold text-ink">{team_a_es}</span>
        </div>
        <span className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.result.vs}
        </span>
        <div className="flex flex-1 flex-col items-center gap-2">
          <FlagImage iso2={flag_b} name={team_b_es} size="lg" className="shadow-sm" />
          <span className="text-center text-lg font-semibold text-ink">{team_b_es}</span>
        </div>
      </div>

      <div className="flex justify-center">
        <span
          className={`rounded-full px-3.5 py-1 text-xs font-medium ${
            isHome ? "bg-brand-soft text-brand" : "bg-canvas text-ink-muted"
          }`}
        >
          {venue_label}
        </span>
      </div>

      <div>
        <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.result.probabilitiesAt90}
        </p>
        <div className="space-y-4">
          {(
            [
              { label: team_a_es, value: p_a, color: TEAM_A },
              { label: t.result.draw, value: p_draw, color: DRAW },
              { label: team_b_es, value: p_b, color: TEAM_B },
            ] as const
          ).map(({ label, value, color }) => (
            <div key={label}>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className="font-medium text-ink">{label}</span>
                <span className="font-semibold" style={{ color }}>
                  {Math.round(value * 100)}%
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-line">
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

      <div className="flex items-center justify-between rounded-xl bg-canvas px-8 py-5">
        <div className="text-center">
          <p className="mb-1 text-xs uppercase tracking-widest text-ink-subtle">
            xG {team_a_es}
          </p>
          <p className="font-mono text-3xl font-bold text-ink">{xg_a.toFixed(1)}</p>
        </div>
        <span className="text-2xl font-light text-line">—</span>
        <div className="text-center">
          <p className="mb-1 text-xs uppercase tracking-widest text-ink-subtle">
            xG {team_b_es}
          </p>
          <p className="font-mono text-3xl font-bold text-ink">{xg_b.toFixed(1)}</p>
        </div>
      </div>

      <Scorelines scorelines={top_scorelines} teamA={team_a_es} teamB={team_b_es} />

      {is_knockout && p_advance_a != null && p_advance_b != null && (
        <div className="space-y-3">
          <div className="flex gap-3">
            <div
              className="flex-1 rounded-xl p-4 text-center"
              style={{ backgroundColor: `${TEAM_A}18` }}
            >
              <p
                className="mb-1 text-xs font-semibold uppercase tracking-widest"
                style={{ color: TEAM_A }}
              >
                {t.result.advancesTeamLabel(team_a_es)}
              </p>
              <p className="text-2xl font-bold" style={{ color: TEAM_A }}>
                {Math.round(p_advance_a * 100)}%
              </p>
            </div>
            <div
              className="flex-1 rounded-xl p-4 text-center"
              style={{ backgroundColor: `${TEAM_B}18` }}
            >
              <p
                className="mb-1 text-xs font-semibold uppercase tracking-widest"
                style={{ color: TEAM_B }}
              >
                {t.result.advancesTeamLabel(team_b_es)}
              </p>
              <p className="text-2xl font-bold" style={{ color: TEAM_B }}>
                {Math.round(p_advance_b * 100)}%
              </p>
            </div>
          </div>
          {p_penalties != null && (
            <p className="text-center text-xs text-ink-muted">
              {t.result.penaltiesProbability}{" "}
              <span className="font-semibold text-ink">
                {Math.round(p_penalties * 100)}%
              </span>
            </p>
          )}
        </div>
      )}

      <div className="rounded-xl bg-canvas px-5 py-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.result.analysis}
        </p>
        <p className="text-sm leading-7 text-ink-muted">{narrative}</p>
      </div>

      <div className="rounded-xl border border-line px-5 py-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
          {t.result.squadFormation}
        </p>
        <div className="space-y-3">
          <FormationRow
            flag={flag_a}
            name={team_a_es}
            confirmed={lineup_confirmed_a}
            desc={squad_desc_a}
          />
          <FormationRow
            flag={flag_b}
            name={team_b_es}
            confirmed={lineup_confirmed_b}
            desc={squad_desc_b}
          />
        </div>
      </div>

      <div className="rounded-xl bg-gold-soft px-6 py-5">
        <p className="text-xs font-semibold uppercase tracking-widest text-gold">
          {t.result.mostLikelyResult}
        </p>
        <div className="mt-2 flex items-center gap-4">
          <div className="flex min-w-0 items-center gap-3">
            {winnerFlag && (
              <FlagImage iso2={winnerFlag} name={winnerName} size="md" className="shadow-sm" />
            )}
            <div className="min-w-0">
              <p className="truncate text-2xl font-bold text-gold">{winnerHeadline}</p>
              <p className="mt-0.5 text-sm text-ink-muted">
                {Math.round(winnerProb * 100)}% · {t.result.confidencePhrase(confidence)}
              </p>
            </div>
          </div>

          {topScore && (
            <div className="ml-auto shrink-0 text-right">
              <p className="text-xs uppercase tracking-widest text-gold">
                {t.result.score}
              </p>
              <p className="text-xl font-bold text-ink">
                {topScore.score_a}–{topScore.score_b}
              </p>
              <p className="text-xs text-ink-muted">
                {Math.round(topScore.probability * 100)}%
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
