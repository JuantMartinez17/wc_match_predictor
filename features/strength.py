"""
features/strength.py
====================
Fuerza ofensiva y defensiva ajustada por rival.

Núcleo del sistema. Estima, mediante una regresión de Poisson ponderada
(marco Maher 1982 / Dixon-Coles 1997), parámetros de ataque y defensa por
selección a partir de los goles observados, controlando por:
  - el rival enfrentado (la defensa/ataque del rival entra como covariable,
    de modo que ganarle a una potencia 'vale' más que a un débil), y
  - la localía (cuando el partido no es neutral).

Cada observación se pondera con `peso = decaimiento_temporal * importancia`.

Ante muestras pequeñas (selecciones ~20 partidos), se aplica SHRINKAGE: el
lambda final mezcla la estimación del GLM con un prior derivado del Elo. Esto
reduce sobreajuste y aporta robustez cuando un equipo tiene pocos datos.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from config import EloConfig, StrengthConfig
from features.elo import _expected_score


class StrengthModel:
    """Modelo de fuerza ofensiva/defensiva ajustada por rival."""

    def __init__(self, cfg: StrengthConfig, elo_cfg: EloConfig) -> None:
        self.cfg = cfg
        self.elo_cfg = elo_cfg
        self._result = None
        self._params: dict[str, float] = {}
        self._teams: set[str] = set()
        self._fallback = False  # True si el GLM no pudo ajustarse

    # ------------------------------------------------------------------ fit
    def fit(self, matches: pd.DataFrame, weights: np.ndarray) -> StrengthModel:
        """
        Ajusta el GLM Poisson ponderado sobre la ventana reciente de partidos.

        `matches` debe contener todas las columnas estándar; `weights` es un
        array alineado con `matches` (un peso por partido).
        """
        if len(matches) != len(weights):
            raise ValueError("`weights` debe alinearse con `matches`.")
        if len(matches) < 6:
            # Muestra insuficiente para identificar el GLM -> sólo prior Elo.
            self._fallback = True
            return self

        long_df = self._to_long(matches, weights)
        self._teams = set(long_df["attack"]).union(long_df["defense"])

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = smf.glm(
                    formula="goals ~ C(attack) + C(defense) + is_home",
                    data=long_df,
                    family=sm.families.Poisson(),
                    freq_weights=long_df["w"].to_numpy(),
                )
                self._result = model.fit(maxiter=200)
            if not np.isfinite(self._result.llf):
                raise ValueError("Log-verosimilitud no finita.")
            self._params = self._result.params.to_dict()
        except Exception:  # noqa: BLE001 -> degradación elegante
            self._result = None
            self._params = {}
            self._fallback = True
        return self

    @staticmethod
    def _to_long(matches: pd.DataFrame, weights: np.ndarray) -> pd.DataFrame:
        """Convierte cada partido en 2 filas (ataque/defensa) para el GLM."""
        home = pd.DataFrame(
            {
                "goals": matches["home_goals"].to_numpy(),
                "attack": matches["home_team"].to_numpy(),
                "defense": matches["away_team"].to_numpy(),
                "is_home": np.where(matches["neutral"].to_numpy(), 0.0, 1.0),
                "w": weights,
            }
        )
        away = pd.DataFrame(
            {
                "goals": matches["away_goals"].to_numpy(),
                "attack": matches["away_team"].to_numpy(),
                "defense": matches["home_team"].to_numpy(),
                "is_home": 0.0,  # el visitante nunca tiene localía
                "w": weights,
            }
        )
        return pd.concat([home, away], ignore_index=True)

    # -------------------------------------------------------------- predict
    def _glm_lambda(self, attack: str, defense: str, is_home: float) -> float | None:
        """Lambda según el GLM, o None si el equipo no está en el ajuste."""
        if self._result is None or attack not in self._teams or defense not in self._teams:
            return None
        # Predicción directa desde los coeficientes (codificación treatment):
        # evita el costo de patsy de `result.predict` por llamada. El .get(...,
        # 0.0) cubre la categoría de referencia, igual que en `team_ratings`.
        try:
            p = self._params
            eta = (
                p.get("Intercept", 0.0)
                + p.get(f"C(attack)[T.{attack}]", 0.0)
                + p.get(f"C(defense)[T.{defense}]", 0.0)
                + p.get("is_home", 0.0) * is_home
            )
            return float(np.exp(eta))
        except Exception:  # noqa: BLE001
            return None

    def _elo_lambda(self, rating_for: float, rating_against: float, is_home: float) -> float:
        """
        Prior de goles esperados derivado del Elo. Mapea la superioridad Elo a
        una ventaja multiplicativa sobre el promedio de goles de la liga.
        """
        ha = self.elo_cfg.home_advantage * is_home
        exp = _expected_score(rating_for + ha, rating_against, self.elo_cfg.scale)
        supremacy = exp - 0.5  # en [-0.5, 0.5]
        k = self.cfg.elo_supremacy_exponent
        return float(self.cfg.league_avg_goals * np.exp(k * supremacy))

    def expected_goals(
        self,
        team_a: str,
        team_b: str,
        ratings: dict[str, float],
        neutral: bool,
        home_team: str | None,
    ) -> tuple[float, float]:
        """
        Goles esperados (lambda) de cada equipo para un partido concreto,
        combinando GLM y prior Elo por shrinkage.

        Returns
        -------
        (lambda_a, lambda_b) : floats positivos.
        """
        is_home_a = 1.0 if (not neutral and home_team == team_a) else 0.0
        is_home_b = 1.0 if (not neutral and home_team == team_b) else 0.0

        ra = ratings.get(team_a, self.elo_cfg.base_rating)
        rb = ratings.get(team_b, self.elo_cfg.base_rating)

        lam_a_elo = self._elo_lambda(ra, rb, is_home_a)
        lam_b_elo = self._elo_lambda(rb, ra, is_home_b)

        lam_a_glm = self._glm_lambda(team_a, team_b, is_home_a)
        lam_b_glm = self._glm_lambda(team_b, team_a, is_home_b)

        blend = self.cfg.elo_prior_blend  # peso del prior Elo (shrinkage)
        lam_a = self._combine(lam_a_glm, lam_a_elo, blend)
        lam_b = self._combine(lam_b_glm, lam_b_elo, blend)

        # Cota inferior para evitar lambdas degenerados.
        return max(lam_a, 0.05), max(lam_b, 0.05)

    @staticmethod
    def _combine(lam_glm: float | None, lam_elo: float, blend: float) -> float:
        """Mezcla geométrica (en log) GLM/Elo. Si no hay GLM, usa sólo Elo."""
        if lam_glm is None or lam_glm <= 0:
            return lam_elo
        log_lambda = (1.0 - blend) * np.log(lam_glm) + blend * np.log(lam_elo)
        return float(np.exp(log_lambda))

    # ------------------------------------------------ estimación de rho (DC)
    def estimate_dixon_coles_rho(
        self,
        matches: pd.DataFrame,
        weights: np.ndarray,
        bounds: tuple[float, float] = (-0.20, 0.20),
        default: float = -0.08,
    ) -> float:
        """
        Estima rho de Dixon-Coles por máxima verosimilitud PONDERADA sobre la
        ventana de entrenamiento, manteniendo fijos los lambda del GLM.

        Sólo la corrección tau de los marcadores bajos depende de rho, así que
        se maximiza  sum_i w_i * log( tau(x_i, y_i; lh_i, la_i, rho) ).

        Devuelve `default` si no hay GLM ajustado (fallback Elo).
        """
        if self._result is None:
            return default

        from scipy.optimize import minimize_scalar

        long = self._to_long(matches, weights)
        n = len(matches)
        try:
            fitted = self._result.predict(long).to_numpy()
        except Exception:  # noqa: BLE001
            return default
        lam_h, lam_a = fitted[:n], fitted[n:]
        x = matches["home_goals"].to_numpy()
        y = matches["away_goals"].to_numpy()
        w = np.asarray(weights, dtype=float)

        # Sólo los partidos con ambos goles <=1 aportan información sobre rho.
        low = (x <= 1) & (y <= 1)
        if low.sum() < 5:
            return default
        xs, ys, lhs, las, ws = x[low], y[low], lam_h[low], lam_a[low], w[low]

        def neg_ll(rho: float) -> float:
            tau = np.ones_like(xs, dtype=float)
            m00 = (xs == 0) & (ys == 0)
            m01 = (xs == 0) & (ys == 1)
            m10 = (xs == 1) & (ys == 0)
            m11 = (xs == 1) & (ys == 1)
            tau[m00] = 1.0 - lhs[m00] * las[m00] * rho
            tau[m01] = 1.0 + lhs[m01] * rho
            tau[m10] = 1.0 + las[m10] * rho
            tau[m11] = 1.0 - rho
            tau = np.clip(tau, 1e-9, None)
            return -float(np.sum(ws * np.log(tau)))

        res = minimize_scalar(neg_ll, bounds=bounds, method="bounded")
        if not res.success or not np.isfinite(res.x):
            return default
        return float(res.x)

    # ------------------------------------------------------ introspección
    def team_ratings(self) -> pd.DataFrame:
        """
        Devuelve ataque/defensa relativos por equipo (centrados), útiles para
        explicar la predicción. Vacío si se usó el fallback Elo.
        """
        if self._result is None:
            return pd.DataFrame(columns=["team", "attack", "defense"])
        params = self._result.params
        rows = []
        for team in sorted(self._teams):
            atk = params.get(f"C(attack)[T.{team}]", 0.0)
            dfn = params.get(f"C(defense)[T.{team}]", 0.0)
            rows.append({"team": team, "attack": atk, "defense": dfn})
        out = pd.DataFrame(rows)
        # Centrado para interpretabilidad (media 0).
        out["attack"] -= out["attack"].mean()
        out["defense"] -= out["defense"].mean()
        return out
