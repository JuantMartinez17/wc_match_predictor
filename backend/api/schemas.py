"""
backend/api/schemas.py
======================
Modelos Pydantic para requests y responses de la API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Team(BaseModel):
    canonical: str
    name_es: str
    flag: str


class FixtureMatch(BaseModel):
    id: str
    date: str        # "2026-06-15"
    time_utc: str    # "20:00"
    team_a: str      # nombre canónico (inglés)
    team_b: str
    team_a_es: str
    team_b_es: str
    flag_a: str
    flag_b: str
    status: str      # "programado" | "en juego" | "finalizado" | ...
    score_a: str
    score_b: str
    neutral: bool
    round: str
    venue: str


class PredictRequest(BaseModel):
    team_a: str = Field(..., description="Nombre en inglés o español (fuzzy matching)")
    team_b: str = Field(..., description="Nombre en inglés o español (fuzzy matching)")
    date: str | None = Field(default=None, description="YYYY-MM-DD; default = hoy")
    knockout: bool = Field(default=False, description="True = modo eliminatoria con penales")
    model: str = Field(default="dixon_coles", description="dixon_coles | bivariate_poisson | poisson_simple")


class ScoreProbability(BaseModel):
    score_a: int
    score_b: int
    probability: float  # 0–1


class PredictResponse(BaseModel):
    # Equipos
    team_a: str
    team_b: str
    team_a_es: str
    team_b_es: str
    flag_a: str
    flag_b: str

    # Probabilidades a 90 min
    p_a: float
    p_draw: float
    p_b: float

    # Goles esperados
    xg_a: float
    xg_b: float

    # Marcadores más probables (top 8)
    top_scorelines: list[ScoreProbability]

    # Sede
    neutral: bool
    home_team: str | None
    venue_label: str

    # Info de plantilla / lineup
    squad_desc_a: str
    squad_desc_b: str

    # Narrativa en español sin jerga estadística
    narrative: str

    # Modo eliminatoria (opcionales)
    is_knockout: bool = False
    p_penalties: float | None = None
    p_advance_a: float | None = None
    p_advance_b: float | None = None
