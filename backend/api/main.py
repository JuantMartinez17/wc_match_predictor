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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import fixture, predict, teams


# ---------------------------------------------------------------------------
# Lifespan — carga del modelo al arrancar (una sola vez)
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="predictor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

    def _load_predictor():
        from data.ingest import build_dataset
        from data.synthetic import generate_team_metadata
        from prediction.predictor import MatchPredictor
        from config import DEFAULT_CONFIG

        matches = build_dataset(since_year=2018)
        metadata = generate_team_metadata(seed=11)
        return MatchPredictor(matches, metadata=metadata, config=DEFAULT_CONFIG)

    print("Cargando modelo predictor...")
    predictor = await loop.run_in_executor(_executor, _load_predictor)
    print("Predictor listo.")

    app.state.predictor = predictor
    app.state.executor = _executor
    yield
    _executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WC 2026 Predictor API",
    version="1.0.0",
    description="API de predicción de partidos — Copa del Mundo 2026",
    lifespan=lifespan,
)

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
_CORS_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router, prefix="/api", tags=["teams"])
app.include_router(fixture.router, prefix="/api", tags=["fixture"])
app.include_router(predict.router, prefix="/api", tags=["predict"])


@app.get("/health", tags=["infra"])
async def health():
    ready = hasattr(app.state, "predictor")
    return {"status": "ok", "predictor": "ready" if ready else "loading"}
