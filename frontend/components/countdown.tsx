"use client";

import { useEffect, useState } from "react";

// Partido inaugural — Copa del Mundo 2026 (ver data/fixture.py: "2026-06-11T20:00Z").
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
      <span className="font-mono text-2xl font-bold tabular-nums text-[#183A70] md:text-3xl">
        {String(value).padStart(2, "0")}
      </span>
      <span className="mt-1 text-[0.625rem] font-semibold uppercase tracking-widest text-[#A8A29E]">
        {label}
      </span>
    </div>
  );
}

export default function Countdown() {
  // Render inicial neutro para evitar mismatch de hidratación; se completa en el cliente.
  const [time, setTime] = useState<Remaining | null>(null);

  useEffect(() => {
    const tick = () => setTime(diff());
    // Primer cálculo en el próximo frame: evita setState sincrónico en el effect
    // y el mismatch de hidratación (el server no conoce la hora del cliente).
    const raf = requestAnimationFrame(tick);
    const id = setInterval(tick, 1000);
    return () => {
      cancelAnimationFrame(raf);
      clearInterval(id);
    };
  }, []);

  if (time?.started) {
    return (
      <div className="flex items-center gap-2.5 rounded-full border border-[#E8E6E1] bg-white px-5 py-2.5 shadow-sm">
        <span className="h-2 w-2 animate-pulse rounded-full bg-[#C95863]" />
        <span className="text-sm font-semibold text-[#1B1B1B]">
          El Mundial ya está en marcha
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-[#E8E6E1] bg-white px-8 py-5 shadow-sm">
      <span className="text-xs font-semibold uppercase tracking-widest text-[#6B6B6B]">
        El Mundial arranca en
      </span>
      <div className="flex items-start gap-5 md:gap-7">
        <Tile value={time?.days ?? 0} label="días" />
        <span className="pt-1 text-2xl font-light text-[#E8E6E1] md:text-3xl">:</span>
        <Tile value={time?.hours ?? 0} label="horas" />
        <span className="pt-1 text-2xl font-light text-[#E8E6E1] md:text-3xl">:</span>
        <Tile value={time?.minutes ?? 0} label="min" />
        <span className="pt-1 text-2xl font-light text-[#E8E6E1] md:text-3xl">:</span>
        <Tile value={time?.seconds ?? 0} label="seg" />
      </div>
    </div>
  );
}
