"""
data/synthetic.py
=================
Generador de datos sintéticos para ejecutar el pipeline de punta a punta sin
depender de un proveedor externo.

IMPORTANTE: en producción se reemplaza por ingestas reales (eloratings.net /
resultados oficiales FIFA, valores de Transfermarkt, partes médicos). El
rendimiento predictivo real depende casi por completo de la CALIDAD DE LOS
DATOS, no del modelo. Este módulo sólo produce datos plausibles y *conectados*
(todos los equipos comparten rivales) para que la regresión de fuerzas sea
identificable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# 32 selecciones con una "fuerza latente" subyacente (sólo para simular; el
# modelo NO la conoce y debe estimarla a partir de resultados).
_TEAMS_LATENT = {
    # CONMEBOL
    "Argentina": 2.05, "Brazil": 1.95, "Colombia": 1.58,
    "Uruguay": 1.60, "Ecuador": 1.36, "Paraguay": 1.42,
    # UEFA
    "France": 2.00, "England": 1.85, "Spain": 1.85, "Portugal": 1.80,
    "Netherlands": 1.75, "Germany": 1.75, "Belgium": 1.70, "Croatia": 1.62,
    "Switzerland": 1.45, "Denmark": 1.44, "Austria": 1.60, "Norway": 1.55,
    "Scotland": 1.50, "Sweden": 1.52, "Czechia": 1.48,
    "Bosnia and Herzegovina": 1.38, "Turkey": 1.48,
    # CAF
    "Morocco": 1.58, "Senegal": 1.46, "Egypt": 1.40, "Algeria": 1.45,
    "Ghana": 1.26, "Tunisia": 1.22, "Côte d'Ivoire": 1.42,
    "South Africa": 1.28, "Congo DR": 1.30, "Cabo Verde": 1.22,
    # AFC
    "Japan": 1.42, "Korea Republic": 1.38, "Iran": 1.24,
    "Australia": 1.30, "Saudi Arabia": 1.18, "Qatar": 1.10,
    "Iraq": 1.32, "Jordan": 1.28, "Uzbekistan": 1.30,
    # CONCACAF
    "Mexico": 1.50, "USA": 1.48, "Canada": 1.28,
    "Panama": 1.30, "Haiti": 1.18, "Curaçao": 1.12,
    # OFC
    "New Zealand": 1.20,
}

_COMPETITIONS = ["world_cup", "continental_cup", "qualifier", "nations_league", "friendly"]
_COMP_PROB = [0.05, 0.10, 0.30, 0.20, 0.35]


def generate_match_history(
    n_matches_per_team: int = 26,
    end_date: str = "2026-06-01",
    seed: int = 7,
) -> pd.DataFrame:
    """
    Genera un historial de partidos sintético pero realista.

    Parameters
    ----------
    n_matches_per_team : int
        Cantidad objetivo de partidos por equipo (se generan pares).
    end_date : str
        Fecha de referencia (ISO). Los partidos se reparten ~3.5 años atrás.
    seed : int
        Semilla para reproducibilidad.

    Returns
    -------
    pd.DataFrame con columnas:
        date, home_team, away_team, home_goals, away_goals,
        competition, neutral
    """
    rng = np.random.default_rng(seed)
    teams = list(_TEAMS_LATENT.keys())
    end = pd.Timestamp(end_date)

    total_matches = int(len(teams) * n_matches_per_team / 2)
    rows = []
    for _ in range(total_matches):
        a, b = rng.choice(teams, size=2, replace=False)
        days_ago = int(rng.integers(1, 365 * 3 + 180))
        date = end - pd.Timedelta(days=days_ago)
        competition = rng.choice(_COMPETITIONS, p=_COMP_PROB)
        neutral = competition in ("world_cup", "continental_cup") and rng.random() < 0.7

        home_adv = 0.0 if neutral else 0.25  # ventaja de localía en goles esperados
        lam_a = np.exp(np.log(_TEAMS_LATENT[a]) - 0.55 * np.log(_TEAMS_LATENT[b]) + home_adv + 0.15)
        lam_b = np.exp(np.log(_TEAMS_LATENT[b]) - 0.55 * np.log(_TEAMS_LATENT[a]) + 0.15)
        ga = rng.poisson(max(lam_a, 0.05))
        gb = rng.poisson(max(lam_b, 0.05))
        rows.append(
            {
                "date": date,
                "home_team": a,
                "away_team": b,
                "home_goals": int(ga),
                "away_goals": int(gb),
                "competition": competition,
                "neutral": bool(neutral),
            }
        )

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def generate_team_metadata(seed: int = 11) -> pd.DataFrame:
    """
    Metadatos por equipo: valor de plantilla (M EUR), valor del once probable,
    y datos del entrenador. Valores plausibles, no reales.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for team, latent in _TEAMS_LATENT.items():
        squad_value = float(np.round((latent**4) * 80 * rng.uniform(0.7, 1.3), 1))
        rows.append(
            {
                "team": team,
                "squad_value_m": squad_value,
                "starting_xi_value_m": float(np.round(squad_value * rng.uniform(0.45, 0.65), 1)),
                "coach_tenure_months": int(rng.integers(2, 60)),
                "coach_matches": int(rng.integers(3, 80)),
                "coach_win_rate": float(np.round(rng.uniform(0.30, 0.72), 3)),
            }
        )
    return pd.DataFrame(rows)


def generate_availability(team: str, scenario: str = "full", seed: int = 0) -> pd.DataFrame:
    """
    Devuelve la lista de jugadores ausentes de un equipo para un partido.

    Cada fila: player, importance (0..1, peso ~ minutos/valor del jugador),
    reason ('injury' | 'suspension' | 'other').
    """
    rng = np.random.default_rng(abs(hash((team, scenario, seed))) % (2**32))
    if scenario == "full":
        n = 0
    elif scenario == "minor":
        n = int(rng.integers(1, 3))
    elif scenario == "key_absences":
        n = int(rng.integers(2, 5))
    else:
        n = 0

    reasons = ["injury", "suspension", "other"]
    rows = []
    for i in range(n):
        importance = float(np.round(rng.uniform(0.25, 0.95), 2))
        rows.append(
            {
                "player": f"{team}_player_{i}",
                "importance": importance,
                "reason": rng.choice(reasons, p=[0.6, 0.25, 0.15]),
            }
        )
    return pd.DataFrame(rows, columns=["player", "importance", "reason"])
