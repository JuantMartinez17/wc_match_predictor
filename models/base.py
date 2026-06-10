"""
models/base.py
==============
Interfaz común de los modelos de marcador y utilidades compartidas para
derivar probabilidades 1X2 y marcadores más probables a partir de una matriz
de probabilidad conjunta P(goles_A = i, goles_B = j).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class ScoreModel(ABC):
    """Modelo que produce la matriz de probabilidad conjunta de marcadores."""

    name: str = "base"

    @abstractmethod
    def score_matrix(self, lambda_a: float, lambda_b: float, max_goals: int) -> np.ndarray:
        """Matriz (max_goals+1, max_goals+1) con P(A=i, B=j). Debe sumar ~1."""
        raise NotImplementedError


def outcome_probabilities(matrix: np.ndarray) -> tuple[float, float, float]:
    """
    Devuelve (P(victoria A), P(empate), P(victoria B)) a partir de la matriz.
    A son filas (i), B son columnas (j).
    """
    p_a = float(np.tril(matrix, -1).sum())  # i > j
    p_draw = float(np.trace(matrix))        # i = j
    p_b = float(np.triu(matrix, 1).sum())   # j > i
    total = p_a + p_draw + p_b
    if total <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return p_a / total, p_draw / total, p_b / total


def top_scorelines(matrix: np.ndarray, k: int = 10) -> list[tuple[int, int, float]]:
    """Lista de los k marcadores más probables: (goles_A, goles_B, prob)."""
    flat = [(i, j, float(matrix[i, j])) for i in range(matrix.shape[0]) for j in range(matrix.shape[1])]
    flat.sort(key=lambda t: t[2], reverse=True)
    return flat[:k]


def expected_goals_from_matrix(matrix: np.ndarray) -> tuple[float, float]:
    """Goles esperados de A y B según la matriz (chequeo de consistencia)."""
    idx = np.arange(matrix.shape[0])
    ea = float((matrix.sum(axis=1) * idx).sum())
    eb = float((matrix.sum(axis=0) * idx).sum())
    return ea, eb
