"""
backend/api/routers/accuracy.py
================================
GET /api/accuracy — métricas de backtesting fuera de muestra por modelo.

Las métricas se calculan UNA VEZ al arrancar (backtest walk-forward sobre
Mundiales 2018 y 2022) y se cachean en disco 30 días. Las peticiones
posteriores son O(1) sobre el caché en memoria.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..schemas import ModelAccuracy

router = APIRouter()

_CACHE_PATH = Path("data/cache/accuracy_metrics.json")
# Baseline versionado (ship con el código, ruta NO ignorada por git). Se sirve
# cuando no hay cache runtime fresco — evita correr el backtest de ~3 min en cada
# arranque con filesystem efímero, que en CPU limitada demora la 1ra predicción.
_BASELINE_PATH = Path(__file__).resolve().parents[1] / "accuracy_baseline.json"
_CACHE_TTL_DAYS = 30
_MODELS_ORDER = ("dixon_coles", "bivariate_poisson", "poisson_simple")
_MODEL_LABELS = {
    "dixon_coles": "Dixon-Coles",
    "bivariate_poisson": "Bivariate Poisson",
    "poisson_simple": "Poisson Simple",
}
_DATASET_LABEL = "Mundiales 2018–2022"


# ---------------------------------------------------------------------------
# Caché en disco
# ---------------------------------------------------------------------------


def _read_metrics(path: Path) -> list[dict] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("metrics")
    except Exception:
        return None


def load_accuracy_cache() -> list[dict] | None:
    """
    Métricas para /api/accuracy, sin correr el backtest al arrancar.

    Prioriza el cache runtime fresco (recalculado en este host); si no existe o
    expiró, cae al baseline versionado (ignorando TTL). Así el backtest de ~3 min
    no corre en producción salvo que se regenere el baseline a mano.
    """
    if _CACHE_PATH.exists():
        age_days = (time.time() - _CACHE_PATH.stat().st_mtime) / 86400
        if age_days <= _CACHE_TTL_DAYS:
            metrics = _read_metrics(_CACHE_PATH)
            if metrics is not None:
                return metrics
    return _read_metrics(_BASELINE_PATH)


def save_accuracy_cache(metrics: list[dict]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metrics": metrics,
    }
    _CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Backtest walk-forward sobre Mundiales 2018–2022
# ---------------------------------------------------------------------------


def _outcome(home_goals: int, away_goals: int) -> int:
    """0 = gana local/A, 1 = empate, 2 = gana visitante/B."""
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def compute_wc_backtest(metadata, config, test_years=(2018, 2022)) -> list[dict]:
    """
    Walk-forward backtest sobre los partidos del Mundial en `test_years`.
    Para cada partido se entrena SOLO con datos anteriores a su fecha.

    Optimización: en lugar de recomputar el Elo histórico por cada partido
    (O(fechas × partidos)), se avanza un único `EloTracker` incremental por
    fecha y se inyecta el estado as-of-fecha en el predictor. Equivalente al
    enfoque por-partido (mismo train y mismo Elo), pero ~10x más rápido.
    """
    import numpy as np
    import pandas as pd

    from data.ingest import build_dataset
    from features.elo import EloTracker
    from prediction.predictor import MatchPredictor
    from validation.metrics import evaluate_all

    print("  [accuracy] Cargando datos para backtest (desde 2006)...")
    all_matches = build_dataset(since_year=2006)
    all_sorted = all_matches.sort_values("date", kind="stable").reset_index(drop=True)
    dates_arr = all_sorted["date"].to_numpy()

    test = (
        all_sorted[
            (all_sorted["competition"] == "world_cup")
            & (all_sorted["date"].dt.year.isin(test_years))
        ]
        .sort_values("date", kind="stable")
        .reset_index(drop=True)
    )

    print(
        f"  [accuracy] {len(test)} partidos de prueba (WC {'+'.join(map(str, test_years))})"
    )

    probs: dict[str, list[list[float]]] = {m: [] for m in _MODELS_ORDER}
    outcomes: list[int] = []

    # El timeline solo afecta las probabilidades si el factor de forma está
    # activo; si no, se omite su construcción (ahorra tiempo en el arranque).
    need_timeline = config.secondary.form_sensitivity > 0
    empty_timeline = pd.DataFrame(columns=["date", "team", "rating"])

    tracker = EloTracker(config.elo, config.importance)
    cursor = 0
    test_dates = sorted(test["date"].unique())
    processed = 0

    for d in test_dates:
        ref_ts = pd.Timestamp(d)
        # Avanza el Elo con todos los partidos estrictamente anteriores a la fecha.
        j = int(np.searchsorted(dates_arr, np.datetime64(ref_ts), side="left"))
        if j > cursor:
            tracker.update(all_sorted.iloc[cursor:j])
            cursor = j

        train = all_sorted.iloc[:j]
        if len(train) < 30:
            continue

        timeline = tracker.timeline() if need_timeline else empty_timeline
        elo_state = (tracker.snapshot_ratings(), timeline)
        try:
            predictor = MatchPredictor(
                train, metadata=metadata, config=config, elo_state=elo_state
            )
        except Exception:
            continue

        ref = str(ref_ts.date())
        day_matches = test[test["date"] == ref_ts]
        for row in day_matches.itertuples(index=False):
            a, b = row.home_team, row.away_team
            neutral = bool(row.neutral)
            home_team = None if neutral else a

            row_probs: dict[str, list[float]] = {}
            ok = True
            for m in _MODELS_ORDER:
                try:
                    pred = predictor.predict(
                        a,
                        b,
                        ref,
                        neutral=neutral,
                        home_team=home_team,
                        model=m,
                        use_simulation=False,
                    )
                    row_probs[m] = [pred.p_a, pred.p_draw, pred.p_b]
                except Exception:
                    ok = False
                    break

            if not ok:
                continue

            outcomes.append(_outcome(int(row.home_goals), int(row.away_goals)))
            for m in _MODELS_ORDER:
                probs[m].append(row_probs[m])
            processed += 1
            if processed % 20 == 0:
                print(f"  [accuracy] {processed}/{len(test)} partidos procesados")

    outcomes_arr = np.array(outcomes, dtype=int)
    result: list[dict] = []

    for m in _MODELS_ORDER:
        arr = np.array(probs[m], dtype=float)
        n = len(arr)
        if n == 0:
            continue
        met = evaluate_all(arr, outcomes_arr[:n])
        result.append(
            {
                "model": m,
                "label": _MODEL_LABELS[m],
                "matches_evaluated": met["n"],
                "correct_result_pct": round(met["accuracy"], 3),
                "brier_score": round(met["brier"], 3),
                "dataset": _DATASET_LABEL,
            }
        )

    print(f"  [accuracy] Backtest completado: {len(outcomes)} partidos evaluados")
    return result


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/accuracy",
    response_model=list[ModelAccuracy],
    summary="Métricas de backtesting por modelo",
    response_description=(
        "Un objeto por modelo (dixon_coles, bivariate_poisson, poisson_simple) "
        "con su porcentaje de acierto y Brier Score sobre partidos del Mundial 2018 y 2022."
    ),
)
async def get_accuracy(request: Request) -> list[ModelAccuracy]:
    """
    Devuelve las métricas de backtesting *walk-forward* fuera de muestra de cada modelo.

    ### Metodología
    Para cada partido del Mundial **2018 y 2022** (test set), el motor se entrena
    únicamente con los datos **anteriores** a ese partido y luego predice.
    No hay fuga de información del futuro.

    ### Métricas
    - **`correct_result_pct`** — porcentaje de partidos en que el modelo acertó
      el resultado 1X2 (victoria local, empate o victoria visitante).
    - **`brier_score`** — error cuadrático multiclase. Mide calibración probabilística.
      Valores típicos en fútbol internacional: 0.19–0.24. Menor es mejor.

    ### Disponibilidad
    Las métricas se sirven desde un baseline versionado que viaja con el código,
    por lo que están disponibles casi inmediatamente tras arrancar. Si por algún
    motivo aún no se cargaron, devuelve `503`.
    """
    metrics = getattr(request.app.state, "accuracy_metrics", None)
    if metrics is None:
        raise HTTPException(
            status_code=503,
            detail="Las métricas se están calculando. Intentá de nuevo en unos minutos.",
        )
    return [ModelAccuracy(**m) for m in metrics]
