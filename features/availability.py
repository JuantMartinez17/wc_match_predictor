"""
features/availability.py
========================
Availability Score: cuantifica el impacto de las ausencias (lesiones,
suspensiones, otras) sobre la fuerza efectiva del equipo.

Idea: una ausencia importa en proporción a la contribución del jugador, no a
su mero número. Aproximamos la contribución por un peso `importance` en [0,1]
(derivable de minutos jugados, share de valor de mercado o titularidad).

    availability = 1 - sum(importance_ausentes) / capacidad_total

Acotado a [min_floor, 1]. Un score < 1 reduce el lambda OFENSIVO del equipo
(ver prediction/predictor.py), nunca lo aumenta. El impacto es deliberadamente
moderado vía `availability_sensitivity` para no dominar el modelo.
"""

from __future__ import annotations

import pandas as pd


def availability_score(
    absences: pd.DataFrame | None,
    squad_importance_capacity: float = 6.0,
    min_floor: float = 0.55,
) -> float:
    """
    Calcula el Availability Score de un equipo.

    Parameters
    ----------
    absences : DataFrame | None
        Filas con al menos la columna 'importance' (0..1). None o vacío => 1.0.
    squad_importance_capacity : float
        'Masa' total de importancia de un plantel sano (normalizador). Mayor =>
        cada ausencia pesa menos. ~6.0 asume que el núcleo de un equipo equivale
        a ~6 unidades de importancia.
    min_floor : float
        Piso del score: ni con muchas bajas un equipo cae por debajo de esto
        (siempre hay reemplazos competitivos a nivel selección).

    Returns
    -------
    float en [min_floor, 1.0].
    """
    if absences is None or len(absences) == 0:
        return 1.0
    if "importance" not in absences.columns:
        raise ValueError("`absences` debe tener columna 'importance'.")

    lost = float(absences["importance"].clip(lower=0.0, upper=1.0).sum())
    score = 1.0 - lost / max(squad_importance_capacity, 1e-6)
    return float(max(min_floor, min(1.0, score)))


def describe_absences(absences: pd.DataFrame | None) -> str:
    """Texto explicativo breve de las bajas, para la salida del modelo."""
    if absences is None or len(absences) == 0:
        return "plantel completo"
    n = len(absences)
    key = (absences["importance"] >= 0.7).sum() if "importance" in absences else 0
    return f"{n} baja(s), {int(key)} de alto impacto"
