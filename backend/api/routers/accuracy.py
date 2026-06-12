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


def load_accuracy_cache() -> list[dict] | None:
    if not _CACHE_PATH.exists():
        return None
    age_days = (time.time() - _CACHE_PATH.stat().st_mtime) / 86400
    if age_days > _CACHE_TTL_DAYS:
        return None
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        return data.get("metrics")
    except Exception:
        return None


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


def compute_wc_backtest(metadata, config) -> list[dict]:
    """
    Walk-forward backtest sobre los partidos del Mundial 2018 y 2022.
    Para cada partido se entrena SOLO con datos anteriores a su fecha.
    """
    import numpy as np

    from data.ingest import build_dataset
    from prediction.predictor import MatchPredictor
    from validation.metrics import evaluate_all

    print("  [accuracy] Cargando datos para backtest (desde 2006)...")
    all_matches = build_dataset(since_year=2006)

    test = all_matches[
        (all_matches["competition"] == "world_cup")
        & (all_matches["date"].dt.year.isin([2018, 2022]))
    ].sort_values("date").reset_index(drop=True)

    print(f"  [accuracy] {len(test)} partidos de prueba (WC 2018+2022)")

    probs: dict[str, list[list[float]]] = {m: [] for m in _MODELS_ORDER}
    outcomes: list[int] = []

    for idx, row in test.iterrows():
        ref = str(row["date"].date())
        train = all_matches[all_matches["date"] < row["date"]]
        if len(train) < 30:
            continue

        a, b = row["home_team"], row["away_team"]
        neutral = bool(row["neutral"])
        home_team = None if neutral else a

        try:
            predictor = MatchPredictor(train, metadata=metadata, config=config)
        except Exception:
            continue

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

        outcomes.append(_outcome(int(row["home_goals"]), int(row["away_goals"])))
        for m in _MODELS_ORDER:
            probs[m].append(row_probs[m])

        if (idx + 1) % 20 == 0:
            print(f"  [accuracy] {idx + 1}/{len(test)} partidos procesados")

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
)
async def get_accuracy(request: Request) -> list[ModelAccuracy]:
    metrics = getattr(request.app.state, "accuracy_metrics", None)
    if metrics is None:
        raise HTTPException(
            status_code=503,
            detail="Las métricas se están calculando. Intentá de nuevo en unos minutos.",
        )
    return [ModelAccuracy(**m) for m in metrics]
