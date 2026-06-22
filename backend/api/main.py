"""
backend/api/main.py
===================
Punto de entrada FastAPI del predictor de partidos — Copa del Mundo 2026.

Correr localmente (desde la raíz del proyecto):
    uvicorn backend.api.main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import accuracy, fixture, predict, standings, teams


def _load_dotenv() -> None:
    """Carga .env desde la raíz del proyecto si existe (desarrollo local)."""
    env_path = Path(__file__).parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


# ---------------------------------------------------------------------------
# Lifespan — carga del modelo al arrancar (una sola vez)
# ---------------------------------------------------------------------------

# 4 workers: con los squad values movidos a cómputo inline, cada request de
# predicción ocupa a lo sumo 2 threads transitorios (lineup HTTP + predicción
# CPU-bound) y el backtest de accuracy ocupa uno al arrancar. 4 da margen sin
# mantener stacks de thread de más en el free tier.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="predictor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

    def _load_predictor():
        from config import DEFAULT_CONFIG
        from data.ingest import build_dataset
        from data.player_ratings import build_real_metadata
        from prediction.predictor import MatchPredictor

        matches = build_dataset(since_year=2018)
        # Metadata real (ratings FIFA): valor de plantilla real y sin factor DT
        # aleatorio. Reemplaza a generate_team_metadata (que era ruido).
        metadata = build_real_metadata()
        return MatchPredictor(matches, metadata=metadata, config=DEFAULT_CONFIG)

    print("Cargando modelo predictor...")
    predictor = await loop.run_in_executor(_executor, _load_predictor)
    print("Predictor listo.")

    app.state.predictor = predictor
    app.state.executor = _executor
    app.state.accuracy_metrics = None  # se llenará al terminar el backtest

    # Pre-calienta el caché de ventana (fit del GLM) para los próximos 8 días,
    # así el primer request de cualquier partido del fixture cercano no paga el
    # ajuste (~200 ms). Las ventanas comparten fecha entre partidos del mismo
    # día, por lo que 8 fits cubren todo el fixture inmediato. Fire-and-forget.
    def _warm_windows():
        from datetime import date, timedelta

        today = date.today()
        for offset in range(8):  # hoy .. hoy+7
            predictor.warm_window(str(today + timedelta(days=offset)))

    loop.run_in_executor(_executor, _warm_windows)

    # Backtest de accuracy en background — no bloquea al predictor principal
    async def _bg_accuracy() -> None:
        from config import DEFAULT_CONFIG

        from .routers.accuracy import (
            compute_wc_backtest,
            load_accuracy_cache,
            save_accuracy_cache,
        )

        cached = await loop.run_in_executor(_executor, load_accuracy_cache)
        if cached is not None:
            app.state.accuracy_metrics = cached
            print("  [accuracy] Métricas cargadas del caché.")
            return

        print("  [accuracy] Calculando métricas de backtesting...")
        # Sin metadata: los ratings FIFA 2025 son anacrónicos para WC 2018/2022.
        # El backtest evalúa el núcleo del motor (Elo + GLM + marcador) sin ruido.
        metrics = await loop.run_in_executor(
            _executor,
            lambda: compute_wc_backtest(None, DEFAULT_CONFIG),
        )
        await loop.run_in_executor(_executor, lambda: save_accuracy_cache(metrics))
        app.state.accuracy_metrics = metrics

    accuracy_task = asyncio.ensure_future(_bg_accuracy())

    yield

    accuracy_task.cancel()
    _executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_TAGS_METADATA = [
    {
        "name": "teams",
        "description": (
            "Lista de los 48 equipos clasificados al Mundial 2026. "
            "**Primer endpoint a consultar** para obtener los IDs numéricos que se pasan a `/api/predict`."
        ),
    },
    {
        "name": "fixture",
        "description": (
            "Fixture oficial del Mundial 2026 vía ESPN API. "
            "Los campos `team_a_id` y `team_b_id` de cada partido se pueden pasar directamente a `/api/predict`. "
            "Caché de 30 minutos; si ESPN no responde, devuelve la última versión guardada."
        ),
    },
    {
        "name": "predict",
        "description": (
            "Motor de predicción probabilística. Devuelve probabilidades 1X2 calibradas, "
            "goles esperados, los 8 marcadores más probables y una narrativa en español. "
            "El motor integra Elo, GLM de fuerza ofensiva/defensiva, modelo de marcador "
            "(Dixon-Coles por defecto) y cálculo exacto de probabilidades sobre la matriz de marcadores. "
            "Cuando el lineup está confirmado (≈1 h antes del partido), incorpora el valor "
            "real del XI y penaliza ausencias de titulares clave."
        ),
    },
    {
        "name": "accuracy",
        "description": (
            "Métricas de backtesting *walk-forward* fuera de muestra. "
            "Se calculan al arrancar el servidor evaluando cada modelo sobre los partidos "
            "del Mundial 2018 y 2022, entrenando únicamente con datos anteriores a cada partido. "
            "El resultado se cachea 30 días en disco."
        ),
    },
    {
        "name": "infra",
        "description": (
            "Health check del servidor. "
            "Hacer polling a `GET /health` al iniciar hasta que `predictor = 'ready'` "
            "(la carga inicial tarda ~30 s)."
        ),
    },
]

app = FastAPI(
    title="WC 2026 Predictor API",
    version="1.1.0",
    description=(
        "API de predicción de resultados para la **Copa del Mundo 2026**.\n\n"
        "Devuelve probabilidades 1X2 calibradas, goles esperados, marcadores más probables "
        "y una narrativa en español para cualquier combinación de los 48 equipos clasificados.\n\n"
        "### Flujo típico de integración\n"
        "1. `GET /health` → polling hasta `predictor = 'ready'`\n"
        "2. `GET /api/teams` → guardar IDs numéricos\n"
        "3. `GET /api/fixture` → partidos con `team_a_id`/`team_b_id` listos para predecir\n"
        "4. `POST /api/predict` → probabilidades + narrativa\n"
        "5. `GET /api/accuracy` → calibración histórica de cada modelo\n\n"
        "### IDs de equipos\n"
        "Todos los endpoints usan **IDs numéricos enteros (1–48)** como identificadores. "
        "Los IDs son estables mientras no cambie el conjunto de equipos clasificados."
    ),
    lifespan=lifespan,
    openapi_tags=_TAGS_METADATA,
)

_load_dotenv()

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
_CORS_ORIGINS = [o.strip().rstrip("/") for o in _raw_origins.split(",") if o.strip()]

# Optional regex for dynamic origins, e.g. Vercel preview deployments:
# https://<project>-git-<branch>-<scope>.vercel.app
# Set CORS_ORIGIN_REGEX in the backend host (Render) to your project's pattern.
_CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router, prefix="/api", tags=["teams"])
app.include_router(fixture.router, prefix="/api", tags=["fixture"])
app.include_router(standings.router, prefix="/api", tags=["standings"])
app.include_router(predict.router, prefix="/api", tags=["predict"])
app.include_router(accuracy.router, prefix="/api", tags=["accuracy"])


@app.get("/health", tags=["infra"])
async def health():
    ready = hasattr(app.state, "predictor")
    return {"status": "ok", "predictor": "ready" if ready else "loading"}
