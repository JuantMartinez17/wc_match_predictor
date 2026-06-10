// Placeholder — el diseño se implementará una vez recibidas las pautas visuales.
// La estructura, tipos y API client ya están listos en:
//   frontend/types/index.ts
//   frontend/lib/api.ts

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-bold">Mundial 2026 — Predictor</h1>
      <p className="text-muted-foreground text-center max-w-md">
        Frontend en construcción. Esperando pautas de diseño.
      </p>
      <div className="mt-4 rounded-lg border p-4 text-sm text-muted-foreground font-mono">
        <p>Backend: <span className="text-foreground">http://localhost:8000</span></p>
        <p>Docs API: <span className="text-foreground">http://localhost:8000/docs</span></p>
      </div>
    </main>
  );
}
