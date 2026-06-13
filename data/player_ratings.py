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
