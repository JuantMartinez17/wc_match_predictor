// Tiny external store for the color theme, read via useSyncExternalStore.
// The initial theme is applied by the inline script in app/layout.tsx before
// hydration; this store reads/writes the `.dark` class on <html> and notifies
// subscribers so the toggle re-renders without setState-in-effect.

const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function subscribeTheme(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function getThemeSnapshot(): boolean {
  return document.documentElement.classList.contains("dark");
}

/** SSR has no DOM — assume light; the client corrects after hydration. */
export function getThemeServerSnapshot(): boolean {
  return false;
}

export function toggleTheme(): void {
  const next = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", next);
  try {
    localStorage.setItem("theme", next ? "dark" : "light");
  } catch {
    // localStorage unavailable (private mode / blocked) — ignore.
  }
  emit();
}
