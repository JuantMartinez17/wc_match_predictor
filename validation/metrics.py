"""
validation/metrics.py
=====================
Métricas de evaluación probabilística para el mercado 1X2.

Codificación de resultados (outcome):
    0 = victoria local / equipo A
    1 = empate
    2 = victoria visitante / equipo B

Métricas:
- log_loss     : verosimilitud negativa media (penaliza confianza errónea).
- brier_score  : error cuadrático multiclase (0 mejor, 2 peor).
- rps          : Ranked Probability Score. Es la métrica de referencia en 1X2
                 porque respeta el ORDEN de los resultados (un error que pone
                 probabilidad en 'empate' es menos grave que ponerla en la
                 derrota cuando ganó el local). Más informativa que Brier aquí.
- accuracy     : aciertos del resultado de máxima probabilidad.
"""

from __future__ import annotations

import numpy as np


def _prep(probs: np.ndarray, outcomes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    if probs.ndim != 2 or probs.shape[1] != 3:
        raise ValueError("`probs` debe ser (n, 3).")
    if len(probs) != len(outcomes):
        raise ValueError("`probs` y `outcomes` deben tener igual longitud.")
    probs = np.clip(probs, 1e-12, 1.0)
    probs = probs / probs.sum(axis=1, keepdims=True)
    return probs, outcomes


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs, outcomes = _prep(probs, outcomes)
    p_true = probs[np.arange(len(outcomes)), outcomes]
    return float(-np.mean(np.log(p_true)))


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs, outcomes = _prep(probs, outcomes)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(outcomes)), outcomes] = 1.0
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Ranked Probability Score promedio (resultado ordenado 0<1<2)."""
    probs, outcomes = _prep(probs, outcomes)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(outcomes)), outcomes] = 1.0
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(onehot, axis=1)
    # Suma sobre las primeras r-1 categorías (r=3 -> 2 términos).
    return float(np.mean(np.sum((cum_p[:, :-1] - cum_o[:, :-1]) ** 2, axis=1)))


def accuracy(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs, outcomes = _prep(probs, outcomes)
    return float(np.mean(np.argmax(probs, axis=1) == outcomes))


def evaluate_all(probs: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    """Devuelve todas las métricas en un diccionario."""
    return {
        "log_loss": log_loss(probs, outcomes),
        "brier": brier_score(probs, outcomes),
        "rps": rps(probs, outcomes),
        "accuracy": accuracy(probs, outcomes),
        "n": int(len(outcomes)),
    }
