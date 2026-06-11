"use client";

import Link from "next/link";
import ThemeToggle from "./theme-toggle";
import LanguageToggle from "./language-toggle";
import { useLanguage } from "@/lib/i18n";

export default function Nav() {
  const { t } = useLanguage();

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      <div className="wc-tricolor h-1 w-full" />
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 md:px-12">
        <Link
          href="/"
          className="font-display text-xl font-extrabold tracking-tight text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 rounded-sm"
        >
          {t.nav.title}
        </Link>
        <nav className="flex items-center gap-4">
          <a
            href="#predictor"
            className="text-sm font-medium text-ink-muted transition-colors hover:text-ink"
          >
            {t.nav.predict}
          </a>
          <a
            href="#fixture"
            className="text-sm font-medium text-ink-muted transition-colors hover:text-ink"
          >
            {t.nav.fixture}
          </a>
          <LanguageToggle />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
