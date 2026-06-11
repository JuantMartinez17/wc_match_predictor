import Nav from "@/components/nav";
import Hero from "@/components/hero";
import PredictorSection from "@/components/predictor-section";
import FixtureSection from "@/components/fixture-section";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <Nav />
      <Hero />
      <PredictorSection />
      <FixtureSection />
    </main>
  );
}