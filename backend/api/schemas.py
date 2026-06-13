"""
backend/api/schemas.py
======================
Modelos Pydantic para requests y responses de la API.
Los `examples` en Field() se usan directamente en el Swagger UI.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Team(BaseModel):
    id: int = Field(
        ...,
        description="ID numérico estable del equipo (1–48). Usar este valor en `/api/predict`.",
        examples=[2],
    )
    canonical: str = Field(
        ...,
        description="Nombre canónico en inglés — referencia interna del motor.",
        examples=["Argentina"],
    )
    name_es: str = Field(
        ...,
        description="Nombre en español listo para mostrar al usuario.",
        examples=["Argentina"],
    )
    flag: str = Field(
        ...,
        description="Código ISO 3166-1 alpha-2 para [flagcdn.com](https://flagcdn.com). "
        "Ej: `'ar'` → `flagcdn.com/w80/ar.png`. England/Scotland usan subdivisiones GB.",
        examples=["ar"],
    )


class FixtureMatch(BaseModel):
    id: str = Field(
        ...,
        description="ID del evento ESPN. Estable para el partido dado.",
        examples=["726321"],
    )
    date: str = Field(
        ...,
        description="Fecha del partido en formato `YYYY-MM-DD`.",
        examples=["2026-06-15"],
    )
    time_utc: str = Field(
        ...,
        description="Hora de inicio en UTC, formato `HH:MM`.",
        examples=["20:00"],
    )
    team_a_id: int = Field(
        ...,
        description="ID numérico del equipo A. Pasar directamente a `POST /api/predict`.",
        examples=[28],
    )
    team_b_id: int = Field(
        ...,
        description="ID numérico del equipo B.",
        examples=[47],
    )
    team_a: str = Field(
        ...,
        description="Nombre canónico en inglés del equipo A (referencia interna).",
        examples=["Mexico"],
    )
    team_b: str = Field(
        ...,
        description="Nombre canónico en inglés del equipo B.",
        examples=["USA"],
    )
    team_a_es: str = Field(
        ...,
        description="Nombre en español del equipo A, listo para mostrar.",
        examples=["México"],
    )
    team_b_es: str = Field(
        ...,
        description="Nombre en español del equipo B.",
        examples=["Estados Unidos"],
    )
    flag_a: str = Field(
        ..., description="Código ISO2 del equipo A para flagcdn.com.", examples=["mx"]
    )
    flag_b: str = Field(..., description="Código ISO2 del equipo B.", examples=["us"])
    status: str = Field(
        ...,
        description=(
            "Estado del partido. Valores posibles: "
            "`programado` | `en juego` | `descanso` | `finalizado` | "
            "`postergado` | `cancelado` | `suspendido`."
        ),
        examples=["programado"],
    )
    score_a: str = Field(
        ...,
        description="Goles marcados por el equipo A. Vacío si el partido no empezó.",
        examples=[""],
    )
    score_b: str = Field(
        ...,
        description="Goles marcados por el equipo B.",
        examples=[""],
    )
    neutral: bool = Field(
        ...,
        description="`false` si uno de los equipos es sede anfitriona y juega como local.",
        examples=[False],
    )
    round: str = Field(
        ...,
        description="Fase del torneo (`group-stage`, `round-of-16`, `quarter-final`, etc.).",
        examples=["group-stage"],
    )
    venue: str = Field(
        ...,
        description="Nombre del estadio.",
        examples=["Estadio Azteca"],
    )


class PredictRequest(BaseModel):
    team_a_id: int = Field(
        ...,
        description="ID numérico del equipo A. Obtenido del campo `id` de `GET /api/teams`.",
        examples=[2],
    )
    team_b_id: int = Field(
        ...,
        description="ID numérico del equipo B. Debe ser distinto de `team_a_id`.",
        examples=[19],
    )
    date: str | None = Field(
        default=None,
        description="Fecha del partido en formato `YYYY-MM-DD`. Si se omite, se usa la fecha de hoy.",
        examples=["2026-06-28"],
    )
    knockout: bool = Field(
        default=False,
        description=(
            "`true` activa el modo eliminatoria: calcula probabilidades a 90 min + prórroga + penales. "
            "Devuelve `p_advance_a`, `p_advance_b` y `p_penalties` adicionales."
        ),
        examples=[False],
    )
    model: str = Field(
        default="dixon_coles",
        description=(
            "Modelo estadístico de marcador a usar:\n"
            "- `dixon_coles` *(recomendado)*: corrige dependencia en marcadores bajos.\n"
            "- `bivariate_poisson`: Poisson bivariado (Karlis & Ntzoufras 2003).\n"
            "- `poisson_simple`: Poisson independiente, baseline de comparación."
        ),
        examples=["dixon_coles"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Fase de grupos",
                    "value": {
                        "team_a_id": 2,
                        "team_b_id": 19,
                        "date": "2026-06-28",
                        "knockout": False,
                        "model": "dixon_coles",
                    },
                }
            ]
        }
    }


class ScoreProbability(BaseModel):
    score_a: int = Field(
        ..., description="Goles del equipo A en este marcador.", examples=[1]
    )
    score_b: int = Field(
        ..., description="Goles del equipo B en este marcador.", examples=[0]
    )
    probability: float = Field(
        ...,
        description="Probabilidad de este marcador exacto (0–1).",
        examples=[0.112],
    )


class ModelAccuracy(BaseModel):
    model: str = Field(
        ...,
        description="Clave interna del modelo de predicción.",
        examples=["dixon_coles"],
    )
    label: str = Field(
        ...,
        description="Nombre legible del modelo para mostrar al usuario.",
        examples=["Dixon-Coles"],
    )
    matches_evaluated: int = Field(
        ...,
        description="Número de partidos evaluados en el backtest walk-forward.",
        examples=[118],
    )
    correct_result_pct: float = Field(
        ...,
        description="Porcentaje de acierto del resultado 1X2 (0–1). Un valor de `0.55` indica acierto en el 55% de los partidos.",
        examples=[0.559],
    )
    brier_score: float = Field(
        ...,
        description=(
            "Brier Score multiclase (0 = perfecto, 2 = peor posible). "
            "Mide calibración probabilística. Valores típicos en fútbol: 0.19–0.24."
        ),
        examples=[0.213],
    )
    dataset: str = Field(
        ...,
        description="Descripción del dataset utilizado en el backtesting.",
        examples=["Mundiales 2018–2022"],
    )


class PredictResponse(BaseModel):
    # ---- Equipos ----
    team_a_id: int = Field(
        ...,
        description="ID numérico del equipo A (mismo que en el request).",
        examples=[2],
    )
    team_b_id: int = Field(..., description="ID numérico del equipo B.", examples=[19])
    team_a: str = Field(
        ...,
        description="Nombre canónico en inglés del equipo A.",
        examples=["Argentina"],
    )
    team_b: str = Field(
        ..., description="Nombre canónico en inglés del equipo B.", examples=["Germany"]
    )
    team_a_es: str = Field(
        ..., description="Nombre en español del equipo A.", examples=["Argentina"]
    )
    team_b_es: str = Field(
        ..., description="Nombre en español del equipo B.", examples=["Alemania"]
    )
    flag_a: str = Field(
        ..., description="Código ISO2 del equipo A para flagcdn.com.", examples=["ar"]
    )
    flag_b: str = Field(..., description="Código ISO2 del equipo B.", examples=["de"])

    # ---- Probabilidades a 90 min ----
    p_a: float = Field(
        ...,
        description="Probabilidad de victoria del equipo A a 90 minutos (0–1). `p_a + p_draw + p_b = 1`.",
        examples=[0.412],
    )
    p_draw: float = Field(
        ..., description="Probabilidad de empate a 90 minutos (0–1).", examples=[0.261]
    )
    p_b: float = Field(
        ...,
        description="Probabilidad de victoria del equipo B a 90 minutos (0–1).",
        examples=[0.327],
    )

    # ---- Goles esperados ----
    xg_a: float = Field(
        ...,
        description="Goles esperados del equipo A según el modelo (expected goals).",
        examples=[1.48],
    )
    xg_b: float = Field(
        ..., description="Goles esperados del equipo B.", examples=[1.21]
    )

    # ---- Marcadores más probables ----
    top_scorelines: list[ScoreProbability] = Field(
        ...,
        description="Top 8 marcadores exactos más probables, ordenados de mayor a menor probabilidad.",
    )

    # ---- Sede ----
    neutral: bool = Field(
        ...,
        description="`false` si uno de los equipos es anfitrión y tiene ventaja de localía.",
        examples=[True],
    )
    home_team_id: int | None = Field(
        ...,
        description="ID del equipo que juega como local. `null` si es cancha neutral.",
        examples=[None],
    )
    venue_label: str = Field(
        ...,
        description="Descripción de la sede lista para mostrar al usuario.",
        examples=["Cancha neutral"],
    )

    # ---- Plantilla / lineup ----
    squad_desc_a: str = Field(
        ...,
        description=(
            "Descripción de la fuente de datos de plantilla del equipo A. "
            "Ejemplos: `'XI confirmado (11 jugadores, 742M EUR)'` o `'plantel completo (680M EUR, XI estimado)'`."
        ),
        examples=["XI confirmado (11 jugadores, 742M EUR)"],
    )
    squad_desc_b: str = Field(
        ...,
        description="Descripción de la fuente de datos de plantilla del equipo B.",
        examples=["plantel completo (510M EUR, XI estimado)"],
    )
    lineup_confirmed_a: bool = Field(
        default=False,
        description="`true` si se obtuvo el 11 inicial confirmado del equipo A desde ESPN.",
        examples=[True],
    )
    lineup_confirmed_b: bool = Field(
        default=False,
        description="`true` si se obtuvo el 11 inicial confirmado del equipo B.",
        examples=[False],
    )
    lineup_a: list[str] | None = Field(
        default=None,
        description=(
            "Nombres del 11 inicial confirmado del equipo A (desde ESPN), en el orden "
            "publicado. `null` cuando el lineup todavía no está disponible (se publica "
            "≈1 h antes del partido) o el partido es a más de 1 día. Presente ⇔ "
            "`lineup_confirmed_a` es `true`."
        ),
        examples=[
            [
                "Emiliano Martínez",
                "Nahuel Molina",
                "Cristian Romero",
                "Lisandro Martínez",
                "Nicolás Tagliafico",
                "Rodrigo De Paul",
                "Enzo Fernández",
                "Alexis Mac Allister",
                "Lionel Messi",
                "Julián Álvarez",
                "Ángel Di María",
            ]
        ],
    )
    lineup_b: list[str] | None = Field(
        default=None,
        description=(
            "Nombres del 11 inicial confirmado del equipo B (desde ESPN). `null` si no "
            "está disponible. Presente ⇔ `lineup_confirmed_b` es `true`."
        ),
        examples=[None],
    )

    # ---- Narrativa ----
    narrative: str = Field(
        ...,
        description=(
            "Resumen del partido en español sin jerga estadística, listo para mostrar al usuario. "
            "Menciona favorito, goles esperados, marcador más probable y forma reciente."
        ),
        examples=[
            "Argentina tiene una leve ventaja, pero el partido está abierto. "
            "Se anticipan entre 2 y 3 goles en total. "
            "El marcador más probable es 1-0 a favor de Argentina (11% de chances)."
        ],
    )

    # ---- Modo eliminatoria (null si knockout=false) ----
    is_knockout: bool = Field(
        default=False,
        description="`true` si se solicitó el modo eliminatoria.",
        examples=[False],
    )
    p_penalties: float | None = Field(
        default=None,
        description="Probabilidad de llegar a la tanda de penales. Solo presente cuando `is_knockout=true`.",
        examples=[None],
    )
    p_advance_a: float | None = Field(
        default=None,
        description=(
            "Probabilidad de que el equipo A clasifique (suma 90 min + prórroga + penales). "
            "Solo presente cuando `is_knockout=true`. `p_advance_a + p_advance_b = 1`."
        ),
        examples=[None],
    )
    p_advance_b: float | None = Field(
        default=None,
        description="Probabilidad de que el equipo B clasifique. Solo presente cuando `is_knockout=true`.",
        examples=[None],
    )
