"use client";

import { useState, useEffect, type ReactNode } from "react";
import { LanguageContext, dictionaries, type Locale } from "@/lib/i18n";

export default function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("es");

  useEffect(() => {
    const stored = localStorage.getItem("locale") as Locale | null;
    if (stored === "en" || stored === "es") setLocaleState(stored);
  }, []);

  useEffect(() => {
    localStorage.setItem("locale", locale);
    document.documentElement.setAttribute("lang", locale);
  }, [locale]);

  return (
    <LanguageContext.Provider
      value={{ locale, setLocale: setLocaleState, t: dictionaries[locale] }}
    >
      {children}
    </LanguageContext.Provider>
  );
}
