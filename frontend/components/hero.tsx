"use client";

import { ArrowRight } from "lucide-react";
import Countdown from "./countdown";
import { useLanguage } from "@/lib/i18n";

export default function Hero() {
  const { t } = useLanguage();

  return (
    <section className="mx-auto flex max-w-7xl flex-col items-center px-6 py-12 text-center md:px-12 md:py-16 lg:py-20">
      <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-ink-muted shadow-sm">
        <span className="wc-tricolor h-2.5 w-2.5 rounded-full" />
        {t.hero.badge}
      </span>

      <h1 className="max-w-2xl font-display text-3xl font-extrabold leading-[1.1] tracking-tight text-ink sm:text-4xl md:text-5xl">
        {t.hero.heading1}{" "}
        <span className="text-brand">{t.hero.heading2}</span>
      </h1>

      <p className="mt-4 max-w-xl text-sm leading-6 text-ink-muted md:text-base">
        {t.hero.description}
      </p>

      <div className="mt-8">
        <Countdown />
      </div>

      <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
        <a
          href="#predictor"
          className="flex items-center gap-2 rounded-xl bg-brand px-7 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
        >
          {t.hero.ctaPredict}
          <ArrowRight size={16} />
        </a>
        <a
          href="#fixture"
          className="rounded-xl border border-line bg-surface px-7 py-3.5 text-[15px] font-semibold text-ink transition-colors hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
        >
          {t.hero.ctaFixture}
        </a>
      </div>
    </section>
  );
}
