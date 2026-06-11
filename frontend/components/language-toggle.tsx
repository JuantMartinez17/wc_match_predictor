"use client";

import { useLanguage } from "@/lib/i18n";

export default function LanguageToggle() {
  const { locale, setLocale } = useLanguage();

  return (
    <button
      type="button"
      onClick={() => setLocale(locale === "es" ? "en" : "es")}
      aria-label={locale === "es" ? "Switch to English" : "Cambiar a español"}
      className="flex items-center gap-1 rounded-sm px-1 py-0.5 text-xs font-semibold tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
    >
      <span className={locale === "es" ? "text-ink" : "text-ink-subtle"}>ES</span>
      <span className="text-line">|</span>
      <span className={locale === "en" ? "text-ink" : "text-ink-subtle"}>EN</span>
    </button>
  );
}
