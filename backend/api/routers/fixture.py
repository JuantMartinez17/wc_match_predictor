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


@router.get("/fixture", response_model=list[FixtureMatch], summary="Fixture del Mundial 2026")
async def get_fixture(
    request: Request,
    days_ahead: int = Query(default=10, ge=1, le=30, description="Días hacia adelante"),
    include_past: int = Query(default=1, ge=0, le=7, description="Días pasados a incluir"),
) -> list[FixtureMatch]:
    from predict import TEAM_EN_TO_ES
    from data.fixture import get_fixture as _get_fixture

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
        result.append(
            FixtureMatch(
                id=m["id"],
                date=m["date"],
                time_utc=m["time_utc"],
                team_a_id=team_id(ta),
                team_b_id=team_id(tb),
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
