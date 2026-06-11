// External store for the UI language, read via useSyncExternalStore.
// Mirrors lib/theme.ts: avoids setState-in-effect and lets the provider stay a
// thin wrapper. During hydration React uses the server snapshot ("es") so the
// SSR markup matches; after hydration it switches to the stored locale.

import type { Locale } from "@/lib/i18n";

const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function subscribeLocale(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function getLocaleSnapshot(): Locale {
  try {
    return localStorage.getItem("locale") === "en" ? "en" : "es";
  } catch {
    return "es";
  }
}

/** SSR has no localStorage — default to Spanish; the client corrects after hydration. */
export function getLocaleServerSnapshot(): Locale {
  return "es";
}

export function setLocale(locale: Locale): void {
  try {
    localStorage.setItem("locale", locale);
  } catch {
    // localStorage unavailable (private mode / blocked) — ignore.
  }
  document.documentElement.setAttribute("lang", locale);
  emit();
}
