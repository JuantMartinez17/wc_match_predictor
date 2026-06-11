"""
backend/api/routers/teams.py
============================
GET /api/teams — lista de los 48 equipos del Mundial 2026 con sus IDs.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..constants import flag, team_id
from ..schemas import Team

router = APIRouter()


@router.get("/teams", response_model=list[Team], summary="Lista de equipos clasificados")
async def get_teams() -> list[Team]:
    from predict import TEAM_EN_TO_ES
    from data.ingest import WC2026_TEAMS

    return [
        Team(
            id=team_id(t),
            canonical=t,
            name_es=TEAM_EN_TO_ES.get(t, t),
            flag=flag(t),
        )
        for t in sorted(WC2026_TEAMS, key=lambda x: TEAM_EN_TO_ES.get(x, x))
    ]
