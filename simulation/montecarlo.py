"""
simulation/montecarlo.py
========================
Simulación Monte Carlo de marcadores a partir de la matriz de probabilidad
conjunta del modelo elegido.

Se muestrea cada partido de forma categórica sobre la grilla de marcadores
(equivale a la distribución exacta truncada del modelo). Esto unifica el
muestreo para Poisson simple, bivariado y Dixon-Coles. Se devuelven tanto las
probabilidades 1X2 estimadas por simulación como la distribución de marcadores,
y se comparan contra la solución exacta de la grilla (deben coincidir salvo
error de Monte Carlo ~ 1/sqrt(N)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.base import outcome_probabilities


@dataclass
class SimulationResult:
    p_home: float
    p_draw: float
    p_away: float
    expected_goals_a: float
    expected_goals_b: float
    top_scorelines: list[tuple[int, int, float]]
    n_simulations: int


def simulate(
    score_matrix: np.ndarray,
    n_simulations: int = 100_000,
    seed: int = 42,
    top_k: int = 10,
) -> SimulationResult:
    """
    Simula `n_simulations` partidos muestreando marcadores de la matriz.

    Parameters
    ----------
    score_matrix : np.ndarray
        Matriz (G+1, G+1) con P(A=i, B=j). Debe sumar ~1.
    n_simulations : int
    seed : int
    top_k : int
        Cantidad de marcadores más probables a reportar.

    Returns
    -------
    SimulationResult
    """
    if score_matrix.ndim != 2 or score_matrix.shape[0] != score_matrix.shape[1]:
        raise ValueError("score_matrix debe ser cuadrada (G+1 x G+1).")
    if n_simulations <= 0:
        raise ValueError("n_simulations debe ser positivo.")

    rng = np.random.default_rng(seed)
    g = score_matrix.shape[0]
    flat = score_matrix.flatten()
    flat = flat / flat.sum()  # normaliza por seguridad

    draws = rng.choice(g * g, size=n_simulations, p=flat)
    goals_a, goals_b = np.divmod(draws, g)

    p_home = float(np.mean(goals_a > goals_b))
    p_draw = float(np.mean(goals_a == goals_b))
    p_away = float(np.mean(goals_a < goals_b))

    # Distribución empírica de marcadores -> top_k.
    pairs, counts = np.unique(np.stack([goals_a, goals_b], axis=1), axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:top_k]
    top = [
        (int(pairs[i, 0]), int(pairs[i, 1]), float(counts[i] / n_simulations))
        for i in order
    ]

    return SimulationResult(
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        expected_goals_a=float(np.mean(goals_a)),
        expected_goals_b=float(np.mean(goals_b)),
        top_scorelines=top,
        n_simulations=n_simulations,
    )


def exact_outcome(score_matrix: np.ndarray) -> tuple[float, float, float]:
    """Solución exacta 1X2 de la grilla (para validar el Monte Carlo)."""
    return outcome_probabilities(score_matrix)
