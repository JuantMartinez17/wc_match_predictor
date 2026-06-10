"""
validation/tuning.py
====================
Optimizador de hiperparámetros por búsqueda en grilla, usando el backtest
walk-forward y minimizando RPS (la métrica rectora del 1X2).

Tunea los parámetros que NO se estiman desde los datos:
  - lambda_decay  (velocidad de olvido temporal)
  - elo_prior_blend (fuerza del shrinkage GLM<->Elo)

(rho de Dixon-Coles se estima por MLE en cada ajuste, así que no se tunea aquí.)

Es deliberadamente honesto sobre el costo: cada combinación corre un backtest
completo, por lo que conviene usar un `test_size` moderado y una grilla acotada.
En producción, ejecutar offline y persistir la mejor configuración.
"""

from __future__ import annotations

import dataclasses
import itertools

import pandas as pd

from config import Config, DEFAULT_CONFIG
from validation.backtest import run_backtest


def tune_hyperparameters(
    matches: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
    base_config: Config = DEFAULT_CONFIG,
    lambda_decay_grid: tuple[float, ...] = (0.40, 0.65, 0.90),
    blend_grid: tuple[float, ...] = (0.20, 0.35, 0.50),
    test_size: int = 60,
    warmup_months: int = 14,
    model: str = "dixon_coles",
    verbose: bool = True,
) -> dict:
    """
    Busca la mejor combinación (lambda_decay, elo_prior_blend) por RPS.

    Returns
    -------
    dict con 'best_config', 'best_rps', 'results' (DataFrame ordenado).
    """
    rows = []
    best = None

    for ld, blend in itertools.product(lambda_decay_grid, blend_grid):
        # Config inmutable -> se reconstruye con los valores de la grilla.
        cfg = dataclasses.replace(
            base_config,
            decay=dataclasses.replace(base_config.decay, lambda_decay=ld),
            strength=dataclasses.replace(base_config.strength, elo_prior_blend=blend),
        )
        bt = run_backtest(
            matches, metadata=metadata, config=cfg,
            test_size=test_size, warmup_months=warmup_months,
            models=(model,), verbose=False,
        )
        rps = bt["metrics"][model]["rps"]
        ll = bt["metrics"][model]["log_loss"]
        rows.append({"lambda_decay": ld, "elo_prior_blend": blend, "rps": rps, "log_loss": ll})
        if verbose:
            print(f"  lambda_decay={ld:.2f}  blend={blend:.2f}  ->  RPS={rps:.4f}")
        if best is None or rps < best["rps"]:
            best = {"lambda_decay": ld, "elo_prior_blend": blend, "rps": rps, "config": cfg}

    results = pd.DataFrame(rows).sort_values("rps").reset_index(drop=True)
    return {
        "best_config": best["config"],
        "best_params": {"lambda_decay": best["lambda_decay"], "elo_prior_blend": best["elo_prior_blend"]},
        "best_rps": best["rps"],
        "results": results,
    }
