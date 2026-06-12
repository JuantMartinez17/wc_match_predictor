"""
backend/api/routers/fixture.py
==============================
GET /api/fixture — fixture oficial del Mundial 2026 vía ESPN API.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request

from ..constants import flag, team_id
from ..schemas import FixtureMatch

router = APIRouter()


@router.get(
    "/fixture",
    response_model=list[FixtureMatch],
    summary="Fixture oficial del Mundial 2026",
    response_description=(
        "Partidos en la ventana [hoy − include_past días, hoy + days_ahead días], "
        "ordenados por fecha y hora UTC."
    ),
)
async def get_fixture(
    request: Request,
    days_ahead: int = Query(
        default=10,
        ge=1,
        le=30,
        description="Días hacia adelante desde hoy a incluir en el fixture.",
        examples=[10],
    ),
    include_past: int = Query(
        default=1,
        ge=0,
        le=7,
        description="Días pasados a incluir (útil para ver resultados recientes).",
        examples=[1],
    ),
) -> list[FixtureMatch]:
    """
    Fixture oficial del Mundial 2026 vía ESPN API pública.

    Devuelve los partidos en la ventana temporal especificada. Los campos
    `team_a_id` y `team_b_id` de cada partido son IDs numéricos que se pueden
    pasar **directamente** a `POST /api/predict` sin ninguna transformación.

    **Caché:** 30 minutos. Si ESPN no está disponible, devuelve la última
    versión cacheada. Los partidos finalizados incluyen `score_a` y `score_b`.
    """
    from data.fixture import get_fixture as _get_fixture
    from predict import TEAM_EN_TO_ES

    loop = asyncio.get_running_loop()
    executor = request.app.state.executor

    raw = await loop.run_in_executor(
        executor,
        lambda: _get_fixture(days_ahead=days_ahead, include_past_days=include_past),
    )

    result: list[FixtureMatch] = []
    for m in raw:
        ta = m["team_a"]
        tb = m["team_b"]
        tid_a = team_id(ta)
        tid_b = team_id(tb)
        if tid_a is None or tid_b is None:
            # Equipo no clasificado al WC2026 — ignorar el partido
            continue
        result.append(
            FixtureMatch(
                id=m["id"],
                date=m["date"],
                time_utc=m["time_utc"],
                team_a_id=tid_a,
                team_b_id=tid_b,
                team_a=ta,
                team_b=tb,
                team_a_es=TEAM_EN_TO_ES.get(ta, ta),
                team_b_es=TEAM_EN_TO_ES.get(tb, tb),
                flag_a=flag(ta),
                flag_b=flag(tb),
                status=m["status"],
                score_a=str(m.get("score_a", "")),
                score_b=str(m.get("score_b", "")),
                neutral=bool(m.get("neutral", True)),
                round=m.get("round", ""),
                venue=m.get("venue", ""),
            )
        )
    return result
