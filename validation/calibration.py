"""
validation/calibration.py
=========================
Calibración de probabilidades. Los modelos Poisson crudos suelen estar
ligeramente descalibrados (demasiado o poco confiados). Aquí:

- reliability_curve: agrupa las predicciones por bins de probabilidad y compara
  probabilidad media predicha vs. frecuencia observada (la 'Calibration Curve').
- TemperatureScaler: recalibrado simple con un único parámetro T que ablanda o
  agudiza las probabilidades (softmax(log p / T)). Se ajusta minimizando log
  loss sobre un conjunto de validación. Barato y efectivo para 1X2.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar

from validation.metrics import log_loss


def reliability_curve(
    probs: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> dict[str, np.ndarray]:
    """
    Curva de calibración sobre la probabilidad de la clase predicha como
    'ganador' de máxima probabilidad (one-vs-rest agregada).

    Returns
    -------
    dict con 'bin_mean_pred', 'bin_obs_freq', 'bin_count'.
    """
    probs = np.clip(np.asarray(probs, dtype=float), 1e-12, 1.0)
    outcomes = np.asarray(outcomes, dtype=int)
    pred_class = np.argmax(probs, axis=1)
    pred_conf = probs[np.arange(len(probs)), pred_class]
    correct = (pred_class == outcomes).astype(float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(pred_conf, edges) - 1, 0, n_bins - 1)

    mean_pred = np.full(n_bins, np.nan)
    obs_freq = np.full(n_bins, np.nan)
    count = np.zeros(n_bins, dtype=int)
    for b in range(n_bins):
        sel = idx == b
        count[b] = int(sel.sum())
        if count[b] > 0:
            mean_pred[b] = pred_conf[sel].mean()
            obs_freq[b] = correct[sel].mean()
    return {"bin_mean_pred": mean_pred, "bin_obs_freq": obs_freq, "bin_count": count}


class TemperatureScaler:
    """Recalibrado por temperatura (un parámetro) para probabilidades 1X2."""

    def __init__(self) -> None:
        self.temperature: float = 1.0

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "TemperatureScaler":
        log_p = np.log(np.clip(probs, 1e-12, 1.0))

        def nll(t: float) -> float:
            t = max(t, 1e-3)
            scaled = np.exp(log_p / t)
            scaled = scaled / scaled.sum(axis=1, keepdims=True)
            return log_loss(scaled, outcomes)

        res = minimize_scalar(nll, bounds=(0.25, 4.0), method="bounded")
        self.temperature = float(res.x)
        return self

    def transform(self, probs: np.ndarray) -> np.ndarray:
        log_p = np.log(np.clip(probs, 1e-12, 1.0))
        scaled = np.exp(log_p / max(self.temperature, 1e-3))
        return scaled / scaled.sum(axis=1, keepdims=True)
