"""
backend/api/routers/fixture.py
==============================
GET /api/fixture — fixture oficial del Mundial 2026 vía ESPN API.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request

from ..constants import flag, team_id
from ..schemas import FixtureMatch, MatchInstance

router = APIRouter()


@router.get(
    "/fixture",
    response_model=list[FixtureMatch],
    summary="Fixture oficial del Mundial 2026",
    response_description=(
        "Si se pasa `instance`: solo los partidos de esa instancia/jornada. Si no: los "
        "partidos en la ventana [hoy − include_past, hoy + days_ahead]. Ordenados por fecha y hora UTC."
    ),
)
async def get_fixture(
    request: Request,
    instance: MatchInstance | None = Query(
        default=None,
        description=(
            "Instancia/jornada del torneo. Si se especifica, la respuesta trae **solo los "
            "partidos de esa instancia** (se ignoran `days_ahead`/`include_past`) — ideal para "
            "que el frontend pida lo justo y no sobrecargue el servidor. Valores: "
            "`fecha-1`, `fecha-2`, `fecha-3` (jornadas de grupos), `dieciseisavos`, `octavos`, "
            "`cuartos`, `semis`, `tercer-puesto`, `final`. Si se omite, se devuelve el rango "
            "por ventana (comportamiento por defecto)."
        ),
        examples=["fecha-1"],
    ),
    days_ahead: int = Query(
        default=10,
        ge=1,
        le=30,
        description="Días hacia adelante desde hoy a incluir. Se ignora si se pasa `instance`.",
        examples=[10],
    ),
    include_past: int = Query(
        default=1,
        ge=0,
        le=40,
        description=(
            "Días pasados a incluir (útil para ver resultados recientes). Se ignora si se "
            "pasa `instance`. El backend nunca consulta antes del inicio del Mundial "
            "(2026-06-11), así que un valor alto (ej. 40) trae el fixture desde el primer día."
        ),
        examples=[1],
    ),
) -> list[FixtureMatch]:
    """
    Fixture oficial del Mundial 2026 vía ESPN API pública.

    Dos modos:
    - **Por instancia** (`?instance=fecha-1`): devuelve solo los partidos de esa
      jornada/ronda. Trae el torneo completo en **una sola llamada cacheada** y
      filtra: liviano para el servidor. Pensado para que el frontend pida por
      instancia y no baje todo el fixture de una.
        - Grupos: `fecha-1`, `fecha-2`, `fecha-3`.
        - Eliminatoria: `dieciseisavos`, `octavos`, `cuartos`, `semis`,
          `tercer-puesto`, `final`.
    - **Por ventana** (sin `instance`): devuelve los partidos en
      [hoy − `include_past`, hoy + `days_ahead`] (comportamiento por defecto).

    Los campos `team_a_id` y `team_b_id` de cada partido son IDs numéricos que se
    pasan **directamente** a `POST /api/predict` sin ninguna transformación.

    **Caché:** 30 min. Si ESPN no está disponible, devuelve la última versión
    cacheada. Los partidos finalizados incluyen `score_a` y `score_b`.

    **Notas:** una ronda de eliminatoria cuyos clasificados aún no se conocen puede
    venir vacía hasta que se definan los equipos. `422` si `instance` no es válida.
    """
    from data.fixture import get_fixture as _get_fixture
    from data.instances import get_fixture_by_instance as _get_by_instance
    from predict import TEAM_EN_TO_ES

    loop = asyncio.get_running_loop()
    executor = request.app.state.executor

    if instance is not None:
        raw = await loop.run_in_executor(
            executor, lambda: _get_by_instance(instance.value)
        )
    else:
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
