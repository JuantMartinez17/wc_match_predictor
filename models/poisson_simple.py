"""
models/poisson_simple.py
========================
Modelo Poisson doble independiente (baseline clásico).

Supone que los goles de A y B son Poisson independientes con medias lambda_a
y lambda_b. Es simple y sorprendentemente competitivo, pero ignora la leve
dependencia entre marcadores y subestima sistemáticamente los empates bajos
(0-0, 1-1). Sirve como término de comparación obligatorio.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson

from models.base import ScoreModel


class SimplePoissonModel(ScoreModel):
    name = "poisson_simple"

    def score_matrix(self, lambda_a: float, lambda_b: float, max_goals: int) -> np.ndarray:
        a = poisson.pmf(np.arange(max_goals + 1), lambda_a)
        b = poisson.pmf(np.arange(max_goals + 1), lambda_b)
        matrix = np.outer(a, b)
        s = matrix.sum()
        return matrix / s if s > 0 else matrix
