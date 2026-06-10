"""
features/elo.py
===============
Cálculo de ratings Elo estilo World Football Elo y de la tendencia reciente.

Notas de diseño (responde a un principio del enunciado):
- El enunciado afirma "Elo es superior al ranking FIFA". Era cierto cuando el
  ranking FIFA usaba el viejo sistema de puntos. Desde 2018 el ranking FIFA ES
  un Elo (fórmula SUM). Mantenemos Elo propio porque permite incorporar margen
  de goles e importancia del partido con control total, y es reproducible.
- La 'tendencia' se mide como la pendiente (OLS) del Elo en los últimos 12 meses.
  Cuidado: con forma temporalmente decaída ya hay solapamiento; aquí se reporta
  como feature interpretable, NO como driver principal de lambda.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import EloConfig, MatchImportanceConfig


def _expected_score(rating_a: float, rating_b: float, scale: float) -> float:
    """Probabilidad esperada de 'éxito' de A en la curva logística de Elo."""
    return 1.0 / (1.0 + 10.0 ** (-(rating_a - rating_b) / scale))


def _goal_difference_multiplier(goal_diff: int) -> float:
    """Multiplicador del K por margen de goles (World Football Elo)."""
    g = abs(goal_diff)
    if g <= 1:
        return 1.0
    if g == 2:
        return 1.5
    return (11.0 + g) / 8.0


def compute_elo_history(
    matches: pd.DataFrame,
    elo_cfg: EloConfig,
    imp_cfg: MatchImportanceConfig,
) -> tuple[dict[str, float], pd.DataFrame]:
    """
    Recorre los partidos cronológicamente y actualiza Elo de cada selección.

    Returns
    -------
    final_ratings : dict[team -> rating]
    timeline : DataFrame con (date, team, rating) tras cada partido, útil para
        calcular tendencia y para depuración.
    """
    ratings: dict[str, float] = {}
    timeline_rows = []

    for _, m in matches.sort_values("date").iterrows():
        home, away = m["home_team"], m["away_team"]
        ra = ratings.get(home, elo_cfg.base_rating)
        rb = ratings.get(away, elo_cfg.base_rating)

        ha = 0.0 if m["neutral"] else elo_cfg.home_advantage
        exp_a = _expected_score(ra + ha, rb, elo_cfg.scale)

        gd = int(m["home_goals"]) - int(m["away_goals"])
        if gd > 0:
            score_a = 1.0
        elif gd == 0:
            score_a = 0.5
        else:
            score_a = 0.0

        k = elo_cfg.k_base * imp_cfg.weights.get(str(m["competition"]), imp_cfg.default)
        k *= _goal_difference_multiplier(gd)

        delta = k * (score_a - exp_a)
        ratings[home] = ra + delta
        ratings[away] = rb - delta

        timeline_rows.append({"date": m["date"], "team": home, "rating": ratings[home]})
        timeline_rows.append({"date": m["date"], "team": away, "rating": ratings[away]})

    timeline = pd.DataFrame(timeline_rows)
    return ratings, timeline


def elo_trend(
    timeline: pd.DataFrame,
    team: str,
    reference_date: pd.Timestamp,
    months: int = 12,
) -> float:
    """
    Pendiente (puntos Elo por año) de la evolución del equipo en los últimos
    `months` meses. Positiva => mejorando; negativa => empeorando; ~0 => estable.
    """
    ref = pd.Timestamp(reference_date)
    cutoff = ref - pd.DateOffset(months=months)
    sub = timeline[
        (timeline["team"] == team)
        & (timeline["date"] >= cutoff)
        & (timeline["date"] < ref)
    ].sort_values("date")
    if len(sub) < 3:
        return 0.0
    t = (sub["date"] - sub["date"].min()).dt.days.to_numpy() / 365.25
    y = sub["rating"].to_numpy()
    if np.allclose(t, t[0]):
        return 0.0
    slope = np.polyfit(t, y, 1)[0]
    return float(slope)


def elo_win_probabilities(
    rating_a: float,
    rating_b: float,
    elo_cfg: EloConfig,
    home_team: str | None = None,
    team_a: str | None = None,
    neutral: bool = True,
    draw_share: float = 0.26,
) -> tuple[float, float, float]:
    """
    Baseline Elo puro -> probabilidades 1X2.

    Convierte la expectativa Elo (que es P(no-derrota) en su forma binaria) en
    triple resultado repartiendo una fracción de empate `draw_share` de forma
    simétrica. Es un baseline deliberadamente simple para comparar.
    """
    ha = 0.0
    if not neutral and home_team is not None and team_a is not None:
        ha = elo_cfg.home_advantage if home_team == team_a else -elo_cfg.home_advantage
    exp_a = _expected_score(rating_a + ha, rating_b, elo_cfg.scale)  # en [0,1]
    p_draw = draw_share * (1.0 - 2.0 * abs(exp_a - 0.5))  # más empate si parejo
    p_a = exp_a - p_draw / 2.0
    p_b = (1.0 - exp_a) - p_draw / 2.0
    # Normaliza por seguridad numérica.
    total = p_a + p_draw + p_b
    return p_a / total, p_draw / total, p_b / total
