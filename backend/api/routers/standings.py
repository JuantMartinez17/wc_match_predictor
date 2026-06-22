"""
backend/api/routers/standings.py
================================
GET /api/standings — tabla de posiciones de la fase de grupos del Mundial 2026.

Los grupos se infieren del calendario (el fixture no expone la letra de grupo) y
las tablas se computan desde los resultados finalizados con desempates FIFA.
Ver data/standings.py.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from ..constants import flag, team_id
from ..schemas import StandingRow, StandingsGroup

router = APIRouter()


@router.get(
    "/standings",
    response_model=list[StandingsGroup],
    summary="Tabla de posiciones de la fase de grupos",
    response_description="12 grupos inferidos del calendario, cada uno con su tabla ordenada.",
)
async def get_standings(request: Request) -> list[StandingsGroup]:
    """
    Devuelve la tabla de posiciones de cada grupo del Mundial 2026.

    Los grupos se **infieren** del propio calendario (componentes conexas de los
    enfrentamientos de fase de grupos), porque el fixture no expone la letra de
    grupo. `group_index` es un identificador estable por orden, no la letra oficial.

    Las tablas se computan solo con partidos finalizados y se ordenan por los
    criterios de desempate de FIFA (puntos, diferencia de goles, goles a favor y
    resultado directo). **Caché:** usa el fixture ya cacheado (refresca una ventana
    amplia en cada llamada; si no hay red, usa lo cacheado).
    """
    from data.fixture import get_fixture
    from data.standings import load_group_standings
    from predict import TEAM_EN_TO_ES

    loop = asyncio.get_running_loop()
    executor = request.app.state.executor

    def _compute():
        # Refresca una ventana amplia (cubre toda la fase de grupos) hacia el
        # caché; get_fixture cae a caché si no hay red. Luego computa desde caché.
        try:
            get_fixture(days_ahead=12, include_past_days=20)
        except Exception:  # noqa: BLE001
            pass
        return load_group_standings()

    groups = await loop.run_in_executor(executor, _compute)

    result: list[StandingsGroup] = []
    for g in groups:
        rows: list[StandingRow] = []
        for r in g["table"]:
            t = r["team"]
            tid = team_id(t)
            if tid is None:
                # Equipo no mapeado a un ID de WC2026: se omite de la tabla.
                continue
            rows.append(
                StandingRow(
                    rank=r["rank"],
                    team_id=tid,
                    team=t,
                    team_es=TEAM_EN_TO_ES.get(t, t),
                    flag=flag(t),
                    played=r["played"],
                    won=r["won"],
                    drawn=r["drawn"],
                    lost=r["lost"],
                    gf=r["gf"],
                    ga=r["ga"],
                    gd=r["gd"],
                    points=r["points"],
                )
            )
        result.append(
            StandingsGroup(group_index=g["group_index"], teams=g["teams"], table=rows)
        )
    return result
