"""
features/context.py
===================
Factores de contexto SECUNDARIOS: valor de plantilla, entrenador e historial
directo. Todos producen ajustes multiplicativos pequeños sobre lambda, acotados
para que NUNCA dominen sobre forma reciente y Elo.

Notas críticas (ver análisis de diseño):
- Valor de plantilla: en la literatura es de los predictores individuales más
  fuertes. Lo mantenemos como secundario por pedido explícito, pero con un techo
  generoso; en producción conviene testear subirle el peso.
- Entrenador: señal débil y en gran medida redundante con la forma reciente
  (el efecto de un DT ya aparece en sus resultados). Peso casi simbólico.
- Historial directo: ruido casi puro entre selecciones (plantillas rotadas).
  Peso mínimo. Se incluye sólo por completitud del enunciado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import SecondaryWeights


def squad_value_multiplier(
    value_a: float,
    value_b: float,
    cfg: SecondaryWeights,
) -> tuple[float, float]:
    """
    Ajuste por valor de plantilla relativo. Devuelve multiplicadores (m_a, m_b)
    centrados en 1.0. El equipo más valioso recibe un leve empujón ofensivo.
    """
    if value_a <= 0 or value_b <= 0:
        return 1.0, 1.0
    log_ratio = np.log(value_a / value_b)
    adj = cfg.squad_value_sensitivity * np.tanh(log_ratio)  # acotado por tanh
    return float(np.exp(adj)), float(np.exp(-adj))


def rest_days(
    matches: pd.DataFrame,
    team: str,
    reference_date: pd.Timestamp,
    max_days: int = 14,
) -> float:
    """
    Días desde el último partido del equipo antes de `reference_date`, topeados a
    `max_days`. Sin historial previo => `max_days` (se asume equipo descansado).

    El tope refleja que la fatiga solo es señal con fixture congestionado (torneo):
    más allá de ~2 semanas el equipo está fresco y descansos mayores no aportan.
    """
    ref = pd.Timestamp(reference_date)
    mask = (
        ((matches["home_team"] == team) | (matches["away_team"] == team))
        & (matches["date"] < ref)
    )
    prev = matches.loc[mask, "date"]
    if len(prev) == 0:
        return float(max_days)
    days = (ref - prev.max()).days
    return float(min(max(days, 0), max_days))


def fatigue_multiplier(
    rest_a: float,
    rest_b: float,
    cfg: SecondaryWeights,
) -> tuple[float, float]:
    """
    Ajuste por fatiga relativa. El equipo con más descanso recibe un leve empujón
    ofensivo; el más cargado, una leve penalización. Devuelve (m_a, m_b) centrados
    en 1.0. Inerte cuando ambos equipos están igual de descansados (diff=0), p. ej.
    en el primer partido de un torneo (ambos topeados a `fatigue_max_days`).
    """
    diff = (rest_a - rest_b) / 7.0  # normaliza por ~1 semana
    adj = cfg.fatigue_sensitivity * np.tanh(diff)
    return float(np.exp(adj)), float(np.exp(-adj))


def coach_multiplier(
    coach_a: dict | None,
    coach_b: dict | None,
    cfg: SecondaryWeights,
) -> tuple[float, float]:
    """
    Ajuste por entrenador. Combina win_rate y experiencia (tenure/partidos) en
    un índice; la diferencia entre equipos produce un ajuste minúsculo.
    """
    def index(c: dict | None) -> float:
        if not c:
            return 0.0
        win = float(c.get("coach_win_rate", 0.5)) - 0.5  # centrado
        exp = np.tanh(float(c.get("coach_matches", 0)) / 40.0) * 0.1
        return win + exp

    diff = index(coach_a) - index(coach_b)
    adj = cfg.coach_sensitivity * np.tanh(diff * 3.0)
    return float(np.exp(adj)), float(np.exp(-adj))


def head_to_head_adjustment(
    matches: pd.DataFrame,
    team_a: str,
    team_b: str,
    reference_date: pd.Timestamp,
    cfg: SecondaryWeights,
    max_meetings: int = 5,
    max_years: int = 10,
) -> tuple[float, float]:
    """
    Ajuste por historial directo: SOLO últimos 5 enfrentamientos y <=10 años,
    con decaimiento temporal. Devuelve multiplicadores (m_a, m_b) muy cercanos
    a 1.0 (peso `h2h_weight`).

    Por qué pesa tan poco: entre selecciones, el H2H tiene utilidad predictiva
    marginal una vez controlada la fuerza (Elo/forma) porque las plantillas
    cambian por completo entre ediciones; usarlo con peso alto introduce ruido
    y sesga hacia la narrativa ('le tiene el número'), no hacia la predicción.
    """
    ref = pd.Timestamp(reference_date)
    cutoff = ref - pd.DateOffset(years=max_years)
    mask = (
        (((matches["home_team"] == team_a) & (matches["away_team"] == team_b))
         | ((matches["home_team"] == team_b) & (matches["away_team"] == team_a)))
        & (matches["date"] >= cutoff)
        & (matches["date"] < ref)
    )
    h2h = matches.loc[mask].sort_values("date", ascending=False).head(max_meetings)
    if len(h2h) == 0:
        return 1.0, 1.0

    score = 0.0  # >0 favorece A
    wsum = 0.0
    for _, m in h2h.iterrows():
        age = (ref - m["date"]).days / 365.25
        w = np.exp(-0.4 * age)
        gd = int(m["home_goals"]) - int(m["away_goals"])
        a_is_home = m["home_team"] == team_a
        a_diff = gd if a_is_home else -gd
        score += w * np.sign(a_diff)
        wsum += w
    if wsum == 0:
        return 1.0, 1.0
    norm = score / wsum  # en [-1, 1]
    adj = cfg.h2h_weight * norm
    return float(np.exp(adj)), float(np.exp(-adj))
