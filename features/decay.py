"""
features/decay.py
=================
Decaimiento temporal exponencial y ponderación por importancia del partido.

El peso final de cada observación combina ambos efectos:

    peso = exp(-lambda * antiguedad_anios) * importancia_competicion

El decaimiento implementa el principio de diseño: los partidos recientes
pesan significativamente más, y los de más de 24 meses se excluyen aguas
arriba (data/loader.filter_recent).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import DecayConfig, MatchImportanceConfig


def time_decay_weight(
    match_dates: pd.Series,
    reference_date: pd.Timestamp,
    lambda_decay: float,
) -> np.ndarray:
    """
    Calcula el peso de decaimiento exponencial: exp(-lambda * antiguedad_anios).

    Parameters
    ----------
    match_dates : pd.Series[datetime]
    reference_date : pd.Timestamp
        Fecha del partido a predecir.
    lambda_decay : float
        Tasa de decaimiento (>0). Mayor => olvida más rápido.

    Returns
    -------
    np.ndarray de pesos en (0, 1].
    """
    if lambda_decay < 0:
        raise ValueError("lambda_decay debe ser >= 0.")
    ref = pd.Timestamp(reference_date)
    age_years = (ref - pd.to_datetime(match_dates)).dt.days.to_numpy() / 365.25
    age_years = np.clip(age_years, 0.0, None)
    return np.exp(-lambda_decay * age_years)


def importance_weight(
    competitions: pd.Series,
    cfg: MatchImportanceConfig,
) -> np.ndarray:
    """Mapea cada competición a su peso de importancia (amistosos << oficiales)."""
    return competitions.map(lambda c: cfg.weights.get(str(c), cfg.default)).to_numpy(dtype=float)


def combined_weights(
    matches: pd.DataFrame,
    reference_date: pd.Timestamp,
    decay_cfg: DecayConfig,
    imp_cfg: MatchImportanceConfig,
) -> np.ndarray:
    """
    Peso final por observación: decaimiento temporal * importancia.

    Se normaliza para que la suma sea igual al n.º de observaciones, de modo
    que actúe como 'frequency weight' interpretable en la regresión Poisson.
    """
    w_time = time_decay_weight(matches["date"], reference_date, decay_cfg.lambda_decay)
    w_imp = importance_weight(matches["competition"], imp_cfg)
    w = w_time * w_imp

    # Boost de recencia in-torneo: partidos de un torneo mayor en curso (mismos
    # `intratournament_days` y competición de tier alto) pesan extra. Inerte
    # cuando no hay torneo mayor reciente (no hay partidos que cumplan la condición)
    # o cuando el boost es 1.0.
    boost = decay_cfg.intratournament_boost
    if boost != 1.0:
        ref = pd.Timestamp(reference_date)
        age_days = (ref - pd.to_datetime(matches["date"])).dt.days.to_numpy()
        recent = (age_days >= 0) & (age_days <= decay_cfg.intratournament_days)
        tier = matches["competition"].isin(decay_cfg.intratournament_competitions).to_numpy()
        w = np.where(recent & tier, w * boost, w)

    if w.sum() <= 0:
        # Degradación elegante: si todo decayó a ~0, usa pesos uniformes.
        return np.ones(len(matches))
    return w * (len(w) / w.sum())
