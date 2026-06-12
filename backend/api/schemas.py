"""
backend/api/schemas.py
======================
Modelos Pydantic para requests y responses de la API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Team(BaseModel):
    id: str  # slug estable: "argentina", "korea-republic", "usa"
    canonical: str  # nombre interno en inglés: "Argentina", "Korea Republic"
    name_es: str  # nombre en español para mostrar al usuario
    flag: str  # emoji bandera


class FixtureMatch(BaseModel):
    id: str
    date: str  # "2026-06-15"
    time_utc: str  # "20:00"
    team_a_id: str  # slug del equipo A — usar para llamar a /api/predict
    team_b_id: str  # slug del equipo B
    team_a: str  # nombre canónico en inglés (para debugging)
    team_b: str
    team_a_es: str  # nombre en español para mostrar
    team_b_es: str
    flag_a: str
    flag_b: str
    status: str  # "programado" | "en juego" | "descanso" | "finalizado" | ...
    score_a: str
    score_b: str
    neutral: bool
    round: str
    venue: str


class PredictRequest(BaseModel):
    team_a_id: str = Field(..., description="ID del equipo A (slug de /api/teams)")
    team_b_id: str = Field(..., description="ID del equipo B (slug de /api/teams)")
    date: str | None = Field(default=None, description="YYYY-MM-DD; default = hoy")
    knockout: bool = Field(
        default=False, description="True = modo eliminatoria con penales"
    )
    model: str = Field(
        default="dixon_coles",
        description="dixon_coles | bivariate_poisson | poisson_simple",
    )


class ScoreProbability(BaseModel):
    score_a: int
    score_b: int
    probability: float  # 0–1


class ModelAccuracy(BaseModel):
    model: str
    label: str
    matches_evaluated: int
    correct_result_pct: float
    brier_score: float
    dataset: str


class PredictResponse(BaseModel):
    # Equipos
    team_a_id: str  # slug — clave estable
    team_b_id: str
    team_a: str  # canónico inglés
    team_b: str
    team_a_es: str  # español para mostrar
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
    home_team_id: str | None  # slug del equipo local, null si es cancha neutral
    venue_label: str

    # Info de plantilla / lineup
    squad_desc_a: str
    squad_desc_b: str
    lineup_confirmed_a: bool = False  # True si hay 11 inicial confirmado
    lineup_confirmed_b: bool = False

    # Narrativa en español sin jerga estadística
    narrative: str

    # Modo eliminatoria (opcionales)
    is_knockout: bool = False
    p_penalties: float | None = None
    p_advance_a: float | None = None
    p_advance_b: float | None = None
