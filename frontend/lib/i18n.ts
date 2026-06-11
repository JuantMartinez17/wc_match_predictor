import { createContext, useContext } from "react";
import type { Translations } from "@/locales/types";
import { es } from "@/locales/es";
import { en } from "@/locales/en";

export type Locale = "es" | "en";
export type { Translations };

export const dictionaries: Record<Locale, Translations> = { es, en };

export type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translations;
};

export const LanguageContext = createContext<LanguageContextValue>({
  locale: "es",
  setLocale: () => {},
  t: es,
});

export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext);
}
