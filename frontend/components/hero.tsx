import { ArrowRight } from "lucide-react";

export default function Hero() {
  return (
    <section className="mx-auto flex max-w-7xl flex-col items-center px-6 py-28 text-center md:px-12 md:py-32">
      <span className="mb-6 rounded-full border border-[#E8E6E1] bg-white px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-[#6B6B6B] shadow-sm">
        FIFA World Cup 2026
      </span>

      <h1 className="max-w-3xl text-5xl font-bold leading-[1.1] tracking-tight text-[#1B1B1B] md:text-7xl">
        Predictor de partidos del{" "}
        <span className="text-[#183A70]">Mundial 2026</span>
      </h1>

      <p className="mt-6 max-w-lg text-base leading-7 text-[#6B6B6B]">
        Probabilidades calibradas con modelos estadísticos sobre datos históricos
        reales. Elegí dos selecciones y obtené un análisis detallado del resultado
        probable.
      </p>

      <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
        <a
          href="#predictor"
          className="flex items-center gap-2 rounded-xl bg-[#183A70] px-7 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-[#224989] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
        >
          Predecir un partido
          <ArrowRight size={16} />
        </a>
        <a
          href="#fixture"
          className="rounded-xl border border-[#E8E6E1] bg-white px-7 py-3.5 text-[15px] font-semibold text-[#1B1B1B] transition-colors hover:bg-[#F8F7F5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
        >
          Ver fixture
        </a>
      </div>
    </section>
  );
}
