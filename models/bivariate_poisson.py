"""
models/bivariate_poisson.py
===========================
Poisson Bivariado (Karlis & Ntzoufras, 2003).

Formulación
-----------
Sean U1 ~ Pois(l1), U2 ~ Pois(l2), U3 ~ Pois(l3) independientes. Se define:

    X (goles A) = U1 + U3
    Y (goles B) = U2 + U3

El término común U3 induce dependencia POSITIVA entre los marcadores.

Momentos:  E[X] = l1 + l3 ,  E[Y] = l2 + l3 ,  Cov(X, Y) = l3.

Función de masa conjunta:

    P(X=x, Y=y) = pois(x; l1) * pois(y; l2) * exp(-l3) * S(x, y)
    S(x, y) = sum_{k=0}^{min(x,y)} C(x,k) C(y,k) k! (l3 / (l1 l2))^k

Parametrización para predicción
-------------------------------
Dadas las medias objetivo lambda_a y lambda_b (de features/strength), y un
parámetro de dependencia l3 (config.bivariate.lambda3_default), fijamos:

    l1 = lambda_a - l3 ,  l2 = lambda_b - l3      (requiere l3 <= min(la, lb))

así las marginales reproducen exactamente los goles esperados.

Supuestos / limitaciones
------------------------
- VENTAJA frente al Poisson doble: captura la covarianza entre marcadores y
  mejora la masa de empates (1-1, 2-2), donde el Poisson independiente falla.
- LIMITACIÓN central: el bivariado de Karlis-Ntzoufras sólo admite l3 >= 0, es
  decir, dependencia NO NEGATIVA. La correlación empírica de goles en fútbol es
  cercana a 0 o levemente negativa, por lo que en muchos datasets Dixon-Coles
  (ver dixon_coles.py) ajusta mejor. Por eso recomendamos DC como modelo
  principal y mantenemos el bivariado por requerimiento y comparación.
- Marginales siguen siendo Poisson (varianza = media); la sobredispersión real
  no se modela (extensión posible: Bivariado Binomial Negativo).
"""

from __future__ import annotations

import numpy as np
from math import comb, factorial
from scipy.stats import poisson

from config import BivariateConfig
from models.base import ScoreModel


class BivariatePoissonModel(ScoreModel):
    name = "bivariate_poisson"

    def __init__(self, cfg: BivariateConfig) -> None:
        self.cfg = cfg

    def _resolve_lambda3(self, lambda_a: float, lambda_b: float) -> float:
        """Acota l3 a [0, min(la, lb) - eps] para mantener l1, l2 > 0."""
        upper = max(min(lambda_a, lambda_b) - 1e-3, 0.0)
        return float(min(max(self.cfg.lambda3_default, 0.0), upper))

    def score_matrix(self, lambda_a: float, lambda_b: float, max_goals: int) -> np.ndarray:
        l3 = self._resolve_lambda3(lambda_a, lambda_b)
        l1 = max(lambda_a - l3, 1e-6)
        l2 = max(lambda_b - l3, 1e-6)

        pa = poisson.pmf(np.arange(max_goals + 1), l1)
        pb = poisson.pmf(np.arange(max_goals + 1), l2)
        r = l3 / (l1 * l2) if l3 > 0 else 0.0
        exp_neg_l3 = np.exp(-l3)

        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                s = 0.0
                for k in range(min(x, y) + 1):
                    s += comb(x, k) * comb(y, k) * factorial(k) * (r ** k)
                matrix[x, y] = pa[x] * pb[y] * exp_neg_l3 * s

        total = matrix.sum()
        return matrix / total if total > 0 else matrix

    def components(self, lambda_a: float, lambda_b: float) -> tuple[float, float, float]:
        """Devuelve (l1, l2, l3) para inspección / simulación generativa."""
        l3 = self._resolve_lambda3(lambda_a, lambda_b)
        return max(lambda_a - l3, 1e-6), max(lambda_b - l3, 1e-6), l3
