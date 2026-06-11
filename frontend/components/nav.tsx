import Link from "next/link";

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 h-16 border-b border-[#E8E6E1] bg-white">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6 md:px-12">
        <Link
          href="/"
          className="text-base font-bold tracking-tight text-[#183A70] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2 rounded-sm"
        >
          WC 2026
        </Link>
        <nav className="flex items-center gap-6">
          <a
            href="#predictor"
            className="text-sm font-medium text-[#6B6B6B] transition-colors hover:text-[#1B1B1B]"
          >
            Predecir
          </a>
          <a
            href="#fixture"
            className="text-sm font-medium text-[#6B6B6B] transition-colors hover:text-[#1B1B1B]"
          >
            Fixture
          </a>
        </nav>
      </div>
    </header>
  );
}
