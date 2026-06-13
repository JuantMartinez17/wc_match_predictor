"""
data/player_ratings.py
======================
Ratings FIFA/EA FC 25 por equipo (0-99 overall) convertidos a M EUR equivalente.

Sirve como reemplazo de SofaScore (actualmente HTTP 403) para alimentar:
  - squad_value_multiplier: ratio de valor entre equipos
  - derive_absences: detecta titulares clave fuera del XI
  - compute_xi_value: suma el valor real del 11 inicial confirmado

Conversión: value_M_EUR = exp((rating - 75) * 0.12) * 15
  - rating 75 → 15 M EUR (referencia: jugador promedio de un equipo mundialista)
  - rating 80 → 27 M EUR
  - rating 87 → 63 M EUR  (Messi — correctamente por encima del valor Transfermarkt)
  - rating 91 → 102 M EUR (Mbappé, Haaland, Vinicius Jr)
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

_RATINGS_PATH = Path(__file__).parent / "wc2026_ratings.json"

_MIN_VALUE = 0.5  # M EUR — suelo para jugadores sin rating


def _rating_to_value(rating: float) -> float:
    return max(_MIN_VALUE, math.exp((rating - 75.0) * 0.12) * 15.0)


@lru_cache(maxsize=1)
def _load_ratings() -> dict[str, dict[str, int]]:
    return json.loads(_RATINGS_PATH.read_text(encoding="utf-8"))


def get_player_ratings(team_canonical: str) -> dict[str, float]:
    """
    Devuelve {nombre_jugador: valor_M_EUR_equiv} para todos los jugadores
    registrados del equipo. Dict vacío si el equipo no está en el dataset.
    """
    all_ratings = _load_ratings()
    team_data = all_ratings.get(team_canonical)
    if not team_data:
        return {}
    return {
        name: round(_rating_to_value(float(rating)), 2)
        for name, rating in team_data.items()
        if name != "_meta"
    }


def build_real_metadata() -> pd.DataFrame:
    """
    Metadata por equipo derivada de los ratings FIFA (no aleatoria).

    Columnas: `team`, `squad_value_m` (suma del plantel registrado) y
    `starting_xi_value_m` (suma del top-11 por valor). Reemplaza a
    `generate_team_metadata`, que producía valores y datos de DT aleatorios:
    el factor entrenador queda neutralizado (sin columnas de DT) y el valor de
    plantilla pasa a reflejar la calidad real de cada selección.
    """
    all_ratings = _load_ratings()
    rows = []
    for team in all_ratings:
        if team == "_meta":
            continue
        values = sorted(get_player_ratings(team).values(), reverse=True)
        if not values:
            continue
        rows.append(
            {
                "team": team,
                "squad_value_m": round(sum(values), 1),
                "starting_xi_value_m": round(sum(values[:11]), 1),
            }
        )
    return pd.DataFrame(rows)
