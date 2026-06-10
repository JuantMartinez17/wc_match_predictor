"""
models/dixon_coles.py
=====================
Modelo Dixon-Coles (1997) — RECOMENDADO como modelo principal.

Parte de dos Poisson independientes y aplica una corrección tau a las cuatro
celdas de marcadores bajos, donde la independencia falla más:

    P(x, y) = tau(x, y; la, lb, rho) * pois(x; la) * pois(y; lb)

    tau(0,0) = 1 - la*lb*rho
    tau(0,1) = 1 + la*rho
    tau(1,0) = 1 + lb*rho
    tau(1,1) = 1 - rho
    tau(x,y) = 1            en cualquier otro caso

Con rho < 0 se incrementa la probabilidad de 0-0 y 1-1 y se reduce la de 1-0 y
0-1, corrigiendo el sesgo del Poisson simple en empates de pocos goles.

Ventaja sobre el bivariado de Karlis-Ntzoufras: rho puede ser negativo, lo que
refleja mejor la (leve) correlación empírica de goles en fútbol. Limitación:
la corrección sólo toca marcadores <=1; el resto de la grilla queda como
Poisson independiente.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson

from config import DixonColesConfig
from models.base import ScoreModel


class DixonColesModel(ScoreModel):
    name = "dixon_coles"

    def __init__(self, cfg: DixonColesConfig) -> None:
        self.cfg = cfg

    def _tau(self, lambda_a: float, lambda_b: float) -> np.ndarray:
        rho = self.cfg.rho
        tau = np.ones((2, 2))
        tau[0, 0] = 1.0 - lambda_a * lambda_b * rho
        tau[0, 1] = 1.0 + lambda_a * rho
        tau[1, 0] = 1.0 + lambda_b * rho
        tau[1, 1] = 1.0 - rho
        # Evita probabilidades negativas si rho es agresivo.
        return np.clip(tau, 1e-6, None)

    def score_matrix(self, lambda_a: float, lambda_b: float, max_goals: int) -> np.ndarray:
        a = poisson.pmf(np.arange(max_goals + 1), lambda_a)
        b = poisson.pmf(np.arange(max_goals + 1), lambda_b)
        matrix = np.outer(a, b)
        tau = self._tau(lambda_a, lambda_b)
        matrix[:2, :2] *= tau
        total = matrix.sum()
        return matrix / total if total > 0 else matrix
