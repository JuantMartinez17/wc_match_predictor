"use client";

import { useState, useEffect, useId } from "react";
import type { FixtureMatch, PredictResponse } from "@/types";
import { fetchFixture, predictMatch } from "@/lib/api";
import PredictionResult from "./prediction-result";
import FlagImage from "./flag-image";
import Modal from "./modal";
import { useLanguage } from "@/lib/i18n";
import { formatLocalTime, localTimeZoneName, localDateString } from "@/lib/datetime";

const STATUS_STYLE: Record<string, string> = {
  "en juego": "text-emerald-700 bg-emerald-50 dark:text-emerald-300/90 dark:bg-emerald-900/20",
  descanso:   "text-amber-700  bg-amber-50  dark:text-amber-300/90  dark:bg-amber-900/20",
  finalizado: "text-ink-muted bg-canvas",
  postergado: "text-danger bg-danger-soft",
  cancelado:  "text-danger bg-danger-soft",
  suspendido: "text-danger bg-danger-soft",
  programado: "text-ink-muted bg-canvas",
};

function formatDay(dateStr: string, dateLocale: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(dateLocale, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function MatchCard({ match }: { match: FixtureMatch }) {
  const { t } = useLanguage();
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();

  const isLive = match.status === "en juego";
  const statusStyle = STATUS_STYLE[match.status] ?? "text-ink-muted bg-canvas";
  const statusLabel = t.fixture.status[match.status] ?? match.status;
  const roundLabel = match.round
    ? (t.fixture.rounds[match.round.toLowerCase()] ?? match.round)
    : "";
  const localTime = formatLocalTime(match.date, match.time_utc, t.meta.dateLocale);
  const tzName = localTimeZoneName(match.date, t.meta.dateLocale);
  const utcTooltip = match.time_utc ? `${match.time_utc} ${t.fixture.utcSuffix}` : "";
  const isFinished = match.status === "finalizado";
  const hasScore =
    match.score_a !== "" &&
    match.score_b !== "" &&
    match.score_a !== "None" &&
    match.score_b !== "None";

  async function handleOpen() {
    setOpen(true);
    if (prediction || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await predictMatch({
        team_a_id: match.team_a_id,
        team_b_id: match.team_b_id,
        date: match.date,
      });
      setPrediction(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.fixture.errorPredict);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div
        className={`overflow-hidden rounded-2xl border bg-surface shadow-[0_1px_3px_rgba(0,0,0,0.06)] ${
          isLive ? "border-danger ring-1 ring-danger" : "border-line"
        }`}
      >
        <div className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-xs text-ink-subtle" title={utcTooltip}>
              {localTime && tzName ? `${localTime} ${tzName}` : localTime}
            </span>
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}
            >
              {isLive && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              )}
              {statusLabel}
            </span>
          </div>

          <div className="flex items-center justify-between gap-2">
            <div className="flex flex-1 flex-col items-center gap-2">
              <FlagImage iso2={match.flag_a} name={match.team_a_es} size="md" />
              <span className="text-center text-sm font-semibold leading-tight text-ink">
                {match.team_a_es}
              </span>
            </div>

            <div className="flex flex-col items-center gap-0.5">
              {hasScore ? (
                <span className="text-2xl font-bold text-ink">
                  {match.score_a} – {match.score_b}
                </span>
              ) : (
                <span className="text-sm font-semibold text-ink-subtle">
                  {t.fixture.vs}
                </span>
              )}
            </div>

            <div className="flex flex-1 flex-col items-center gap-2">
              <FlagImage iso2={match.flag_b} name={match.team_b_es} size="md" />
              <span className="text-center text-sm font-semibold leading-tight text-ink">
                {match.team_b_es}
              </span>
            </div>
          </div>

          {(roundLabel || match.venue) && (
            <p className="mt-3 text-center text-xs text-ink-subtle">
              {[roundLabel, match.venue].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>

        <div className="border-t border-line px-6 py-3">
          <button
            type="button"
            onClick={handleOpen}
            className="w-full rounded-sm text-center text-xs font-semibold uppercase tracking-widest text-brand transition-colors hover:text-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
          >
            {isFinished ? t.fixture.viewAnalysis : t.fixture.viewPrediction}
          </button>
        </div>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        labelledBy={titleId}
        header={
          <div className="min-w-0">
            <h3 id={titleId} className="truncate text-base font-semibold text-ink">
              {match.team_a_es}{" "}
              <span className="font-normal text-ink-subtle">{t.fixture.vs}</span>{" "}
              {match.team_b_es}
            </h3>
            <p className="mt-0.5 truncate text-xs capitalize text-ink-subtle">
              {[
                formatDay(match.date, t.meta.dateLocale),
                localTime && tzName ? `${localTime} ${tzName}` : localTime,
                roundLabel,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
        }
      >
        {loading && (
          <div className="flex justify-center py-16">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-line border-t-brand" />
          </div>
        )}
        {error && (
          <div className="py-8">
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
              {error}
            </p>
            <button
              type="button"
              onClick={handleOpen}
              className="mt-4 rounded-xl border border-line px-5 py-2.5 text-sm font-semibold text-ink-muted transition-colors hover:bg-canvas"
            >
              {t.fixture.retry}
            </button>
          </div>
        )}
        {prediction && !loading && <PredictionResult result={prediction} />}
      </Modal>
    </>
  );
}

export default function FixtureSection() {
  const { t } = useLanguage();
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
          setError(e instanceof Error ? e.message : t.fixture.errorLoad);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [daysAhead, t.fixture.errorLoad]);

  const grouped = matches.reduce<Record<string, FixtureMatch[]>>((acc, m) => {
    const key = localDateString(m.date, m.time_utc);
    if (!acc[key]) acc[key] = [];
    acc[key].push(m);
    return acc;
  }, {});
  const sortedDates = Object.keys(grouped).sort();

  function relativeLabel(dateStr: string): string | null {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const todayLocal = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const tmrw = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const tomorrowLocal = `${tmrw.getFullYear()}-${pad(tmrw.getMonth() + 1)}-${pad(tmrw.getDate())}`;
    if (dateStr === todayLocal) return t.fixture.today;
    if (dateStr === tomorrowLocal) return t.fixture.tomorrow;
    return null;
  }

  return (
    <section id="fixture" className="mx-auto max-w-7xl px-6 py-20 md:px-12">
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        {t.fixture.sectionLabel}
      </p>
      <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink md:text-4xl">
        {t.fixture.heading}
      </h2>
      <p className="mt-2 text-sm leading-6 text-ink-muted">
        {t.fixture.description}
      </p>

      {loading && (
        <div className="mt-12 flex justify-center">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-brand" />
        </div>
      )}

      {error && (
        <p className="mt-8 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {!loading && !error && matches.length === 0 && (
        <p className="mt-8 text-sm text-ink-subtle">{t.fixture.emptyState}</p>
      )}

      {!loading && sortedDates.length > 0 && (
        <div className="mt-10 space-y-10">
          {sortedDates.map((date) => (
            <div key={date}>
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold capitalize text-ink-muted">
                {relativeLabel(date) && (
                  <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide text-brand">
                    {relativeLabel(date)}
                  </span>
                )}
                {formatDay(date, t.meta.dateLocale)}
              </h3>
              <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {grouped[date].map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && matches.length > 0 && daysAhead < 30 && (
        <div className="mt-10 flex justify-center">
          <button
            type="button"
            onClick={() => setDaysAhead((v) => Math.min(v + 7, 30))}
            className="rounded-xl border border-line bg-surface px-7 py-3 text-sm font-semibold text-ink-muted transition-colors hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
          >
            {t.fixture.loadMore}
          </button>
        </div>
      )}
    </section>
  );
}
