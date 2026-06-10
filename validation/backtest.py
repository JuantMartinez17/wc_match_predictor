"""
validation/backtest.py
======================
Backtesting walk-forward (out-of-sample temporal). Para cada partido de prueba
se reentrena usando ÚNICAMENTE datos anteriores a su fecha y se predice, sin
fuga de información. Luego se calculan métricas por modelo y se comparan:

    - Elo puro (baseline)
    - Poisson simple (independiente)
    - Poisson Bivariado
    - Dixon-Coles

Este es el módulo correcto donde re-optimizar hiperparámetros (lambda_decay,
rho, blend, etc.) por validación temporal antes de producción.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import Config, DEFAULT_CONFIG
from models.elo_model import EloBaseline
from prediction.predictor import MatchPredictor
from validation.metrics import evaluate_all


def _outcome(home_goals: int, away_goals: int) -> int:
    """0 = gana local/A, 1 = empate, 2 = gana visitante/B."""
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def run_backtest(
    matches: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
    config: Config = DEFAULT_CONFIG,
    test_size: int = 150,
    warmup_months: int = 18,
    models: tuple[str, ...] = ("poisson_simple", "bivariate_poisson", "dixon_coles"),
    verbose: bool = True,
) -> dict:
    """
    Ejecuta el backtest y devuelve métricas por modelo más los arrays de
    probabilidades y resultados (para curvas de calibración).

    Parameters
    ----------
    test_size : int
        Cantidad de partidos más recientes a evaluar fuera de muestra.
    warmup_months : int
        Mínimo de historia requerido antes del primer partido de prueba.
    """
    matches = matches.sort_values("date").reset_index(drop=True)
    first_date = matches["date"].min() + pd.DateOffset(months=warmup_months)
    eligible = matches[matches["date"] >= first_date].reset_index(drop=True)
    test = eligible.tail(test_size).reset_index(drop=True)

    if len(test) == 0:
        raise ValueError("No hay partidos suficientes para backtesting con esa configuración.")

    elo_baseline = EloBaseline(config.elo)
    probs = {m: [] for m in models}
    probs["elo_pure"] = []
    outcomes: list[int] = []

    for i, row in test.iterrows():
        ref = row["date"]
        train = matches[matches["date"] < ref]
        if len(train) < 30:
            continue
        a, b = row["home_team"], row["away_team"]
        neutral = bool(row["neutral"])
        home_team = None if neutral else a

        try:
            predictor = MatchPredictor(train, metadata=metadata, config=config)
        except Exception:  # noqa: BLE001
            continue

        # Elo puro
        ra = predictor.ratings.get(a, config.elo.base_rating)
        rb = predictor.ratings.get(b, config.elo.base_rating)
        probs["elo_pure"].append(
            list(elo_baseline.predict_1x2(ra, rb, neutral=neutral, home_team=home_team, team_a=a))
        )

        # Modelos de marcador (camino exacto, sin Monte Carlo para velocidad)
        for m in models:
            pred = predictor.predict(
                a, b, ref, neutral=neutral, home_team=home_team,
                model=m, use_simulation=False,
            )
            probs[m].append([pred.p_a, pred.p_draw, pred.p_b])

        outcomes.append(_outcome(int(row["home_goals"]), int(row["away_goals"])))

        if verbose and (i + 1) % 25 == 0:
            print(f"  backtest: {i + 1}/{len(test)} partidos evaluados")

    outcomes_arr = np.array(outcomes, dtype=int)
    results = {}
    for name, plist in probs.items():
        arr = np.array(plist, dtype=float)
        if len(arr) == 0:
            continue
        results[name] = evaluate_all(arr, outcomes_arr[: len(arr)])

    return {
        "metrics": results,
        "probs": {k: np.array(v, dtype=float) for k, v in probs.items()},
        "outcomes": outcomes_arr,
        "n_test": len(outcomes_arr),
    }


def metrics_table(results: dict) -> pd.DataFrame:
    """Convierte el dict de métricas en una tabla ordenada por RPS (menor mejor)."""
    df = pd.DataFrame(results["metrics"]).T
    cols = ["log_loss", "brier", "rps", "accuracy", "n"]
    df = df[[c for c in cols if c in df.columns]]
    return df.sort_values("rps")
