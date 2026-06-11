"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/lib/i18n";

const KICKOFF = new Date("2026-06-11T20:00:00Z");

interface Remaining {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  started: boolean;
}

function diff(): Remaining {
  const ms = KICKOFF.getTime() - Date.now();
  if (ms <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, started: true };
  }
  const total = Math.floor(ms / 1000);
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
    started: false,
  };
}

function Tile({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="font-mono text-2xl font-bold tabular-nums text-brand md:text-3xl">
        {String(value).padStart(2, "0")}
      </span>
      <span className="mt-1 text-[0.625rem] font-semibold uppercase tracking-widest text-ink-subtle">
        {label}
      </span>
    </div>
  );
}

export default function Countdown() {
  const { t } = useLanguage();
  const [time, setTime] = useState<Remaining | null>(null);

  useEffect(() => {
    const tick = () => setTime(diff());
    const raf = requestAnimationFrame(tick);
    const id = setInterval(tick, 1000);
    return () => {
      cancelAnimationFrame(raf);
      clearInterval(id);
    };
  }, []);

  if (time?.started) {
    return (
      <div className="flex items-center gap-2.5 rounded-full border border-line bg-surface px-5 py-2.5 shadow-sm">
        <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
        <span className="text-sm font-semibold text-ink">{t.countdown.started}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface px-8 py-5 shadow-sm">
      <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
        {t.countdown.label}
      </span>
      <div className="flex items-start gap-5 md:gap-7">
        <Tile value={time?.days ?? 0} label={t.countdown.days} />
        <span className="pt-1 text-2xl font-light text-line md:text-3xl">:</span>
        <Tile value={time?.hours ?? 0} label={t.countdown.hours} />
        <span className="pt-1 text-2xl font-light text-line md:text-3xl">:</span>
        <Tile value={time?.minutes ?? 0} label={t.countdown.min} />
        <span className="pt-1 text-2xl font-light text-line md:text-3xl">:</span>
        <Tile value={time?.seconds ?? 0} label={t.countdown.sec} />
      </div>
    </div>
  );
}
