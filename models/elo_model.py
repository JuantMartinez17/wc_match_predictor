"""
models/elo_model.py
===================
Baseline Elo puro -> 1X2, sin marcadores. Sirve únicamente como término de
comparación en la validación (no produce distribución de goles).
"""

from __future__ import annotations

from config import EloConfig
from features.elo import elo_win_probabilities


class EloBaseline:
    name = "elo_pure"

    def __init__(self, cfg: EloConfig) -> None:
        self.cfg = cfg

    def predict_1x2(
        self,
        rating_a: float,
        rating_b: float,
        neutral: bool = True,
        home_team: str | None = None,
        team_a: str | None = None,
    ) -> tuple[float, float, float]:
        """Devuelve (P_A, P_empate, P_B)."""
        return elo_win_probabilities(
            rating_a,
            rating_b,
            self.cfg,
            home_team=home_team,
            team_a=team_a,
            neutral=neutral,
        )
