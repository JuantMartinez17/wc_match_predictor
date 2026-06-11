import Link from "next/link";

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      {/* WC2026 identity signature — host-nation tricolor */}
      <div className="wc-tricolor h-1 w-full" />
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 md:px-12">
        <Link
          href="/"
          className="font-display text-xl font-extrabold tracking-tight text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 rounded-sm"
        >
          Mundial 2026
        </Link>
        <nav className="flex items-center gap-6">
          <a
            href="#predictor"
            className="text-sm font-medium text-ink-muted transition-colors hover:text-ink"
          >
            Predecir
          </a>
          <a
            href="#fixture"
            className="text-sm font-medium text-ink-muted transition-colors hover:text-ink"
          >
            Fixture
          </a>
        </nav>
      </div>
    </header>
  );
}
