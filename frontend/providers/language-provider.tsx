"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { LanguageContext, dictionaries } from "@/lib/i18n";
import {
  subscribeLocale,
  getLocaleSnapshot,
  getLocaleServerSnapshot,
  setLocale,
} from "@/lib/locale";

export default function LanguageProvider({ children }: { children: ReactNode }) {
  const locale = useSyncExternalStore(
    subscribeLocale,
    getLocaleSnapshot,
    getLocaleServerSnapshot
  );

  return (
    <LanguageContext.Provider
      value={{ locale, setLocale, t: dictionaries[locale] }}
    >
      {children}
    </LanguageContext.Provider>
  );
}
