"""
backend/api/routers/predict.py
==============================
POST /api/predict — predicción de un partido del Mundial 2026.
"""

from __future__ import annotations

import asyncio
import difflib
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from ..constants import flag
from ..schemas import PredictRequest, PredictResponse, ScoreProbability

router = APIRouter()


# ---------------------------------------------------------------------------
# Resolución de nombre sin sys.exit (versión API-safe de predict.resolve_team)
# ---------------------------------------------------------------------------

def _resolve_team(name: str) -> str | None:
    from predict import TEAM_EN_TO_ES, TEAM_ES_TO_EN
    from data.ingest import WC2026_TEAMS

    lower = name.strip().lower()

    if lower in TEAM_ES_TO_EN:
        return TEAM_ES_TO_EN[lower]

    for team in WC2026_TEAMS:
        if team.lower() == lower:
            return team

    all_es = list(TEAM_EN_TO_ES.values())
    partial_es = [n for n in all_es if lower in n.lower()]
    if len(partial_es) == 1:
        return TEAM_ES_TO_EN[partial_es[0].lower()]

    partial_en = [t for t in WC2026_TEAMS if lower in t.lower()]
    if len(partial_en) == 1:
        return partial_en[0]

    close_es = difflib.get_close_matches(name.strip(), all_es, n=1, cutoff=0.4)
    if close_es:
        return TEAM_ES_TO_EN[close_es[0].lower()]

    close_en = difflib.get_close_matches(name.strip(), list(WC2026_TEAMS), n=1, cutoff=0.4)
    if close_en:
        return close_en[0]

    return None


# ---------------------------------------------------------------------------
# Narrativa en lenguaje simple (misma lógica que app.py, sin dependencia Streamlit)
# ---------------------------------------------------------------------------

def _build_narrative(
    team_a: str,
    team_b: str,
    p_a: float,
    p_draw: float,
    p_b: float,
    xg_a: float,
    xg_b: float,
    top_scorelines: list,
    trend_a: float,
    trend_b: float,
    venue_label: str,
) -> str:
    from predict import TEAM_EN_TO_ES

    nombre_a = TEAM_EN_TO_ES.get(team_a, team_a)
    nombre_b = TEAM_EN_TO_ES.get(team_b, team_b)
    partes: list[str] = []

    # Favorito
    if p_a >= 0.62:
        partes.append(f"{nombre_a} llega como gran favorito ante {nombre_b}.")
    elif p_b >= 0.62:
        partes.append(f"{nombre_b} llega como gran favorito ante {nombre_a}.")
    elif p_a >= 0.50:
        partes.append(f"{nombre_a} tiene una leve ventaja, pero el partido está abierto.")
    elif p_b >= 0.50:
        partes.append(f"{nombre_b} tiene una leve ventaja, pero el partido está abierto.")
    else:
        partes.append(f"Partido muy parejo entre {nombre_a} y {nombre_b}.")

    # Sede
    if "sede" in venue_label.lower():
        partes.append("Además, juega con el apoyo de su hinchada.")

    # Goles esperados
    total = xg_a + xg_b
    if total < 1.9:
        partes.append("Se espera un partido cerrado, con pocos goles.")
    elif total < 2.7:
        partes.append("Se anticipan entre 2 y 3 goles en total.")
    else:
        partes.append("Hay chances de que sea un partido con varios goles.")

    # Resultado más probable
    if top_scorelines:
        ga, gb, p_top = top_scorelines[0]
        if ga == gb:
            partes.append(
                f"El resultado más probable es un empate {ga}-{gb} ({p_top*100:.0f}% de chances)."
            )
        elif ga > gb:
            partes.append(
                f"El marcador más probable es {ga}-{gb} a favor de {nombre_a} ({p_top*100:.0f}% de chances)."
            )
        else:
            partes.append(
                f"El marcador más probable es {gb}-{ga} a favor de {nombre_b} ({p_top*100:.0f}% de chances)."
            )

    # Forma reciente
    if trend_a > 50 and trend_b <= 10:
        partes.append(f"{nombre_a} viene en un gran momento de forma.")
    elif trend_b > 50 and trend_a <= 10:
        partes.append(f"{nombre_b} viene en un gran momento de forma.")
    elif trend_a > 50 and trend_b > 50:
        partes.append("Ambos equipos vienen en buen momento de forma.")
    elif trend_a < -50 and trend_b > 10:
        partes.append(f"{nombre_a} llega con cierta irregularidad reciente.")
    elif trend_b < -50 and trend_a > 10:
        partes.append(f"{nombre_b} llega con cierta irregularidad reciente.")

    return " ".join(partes)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=PredictResponse, summary="Predecir resultado de un partido")
async def predict_match(req: PredictRequest, request: Request) -> PredictResponse:
    predictor = request.app.state.predictor
    executor = request.app.state.executor
    loop = asyncio.get_running_loop()

    # Resolver nombres
    team_a = _resolve_team(req.team_a)
    team_b = _resolve_team(req.team_b)
    if team_a is None:
        raise HTTPException(status_code=422, detail=f"Equipo no encontrado: '{req.team_a}'")
    if team_b is None:
        raise HTTPException(status_code=422, detail=f"Equipo no encontrado: '{req.team_b}'")
    if team_a == team_b:
        raise HTTPException(status_code=422, detail="Los dos equipos deben ser distintos.")

    ref_date = req.date or str(date.today())

    # Venue
    from predict import detect_venue, _resolve_xi_value
    from predict import TEAM_EN_TO_ES

    neutral, home_team = detect_venue(team_a, team_b)
    venue_label = (
        f"Local: {TEAM_EN_TO_ES.get(home_team, home_team)} (sede del Mundial)"
        if not neutral and home_team
        else "Cancha neutral"
    )

    # Fetch squad values + lineup concurrentemente (I/O bloqueante → thread pool)
    def _squads_and_lineup():
        from predict import _fetch_squad_values, _fetch_lineup
        sq_a = _fetch_squad_values(team_a)
        sq_b = _fetch_squad_values(team_b)
        lineup = _fetch_lineup(team_a, team_b, ref_date)
        return sq_a, sq_b, lineup

    squad_a, squad_b, lineup = await loop.run_in_executor(executor, _squads_and_lineup)

    lineup_a = lineup["team_a"] if lineup else None
    lineup_b = lineup["team_b"] if lineup else None
    xi_val_a, xi_desc_a = _resolve_xi_value(team_a, lineup_a, squad_a)
    xi_val_b, xi_desc_b = _resolve_xi_value(team_b, lineup_b, squad_b)

    # Predicción (CPU-bound → thread pool)
    def _run_predict():
        if req.knockout:
            return predictor.predict_knockout(
                team_a, team_b, ref_date,
                neutral=neutral, home_team=home_team, model=req.model,
                squad_value_a=xi_val_a, squad_value_b=xi_val_b,
            )
        return predictor.predict(
            team_a, team_b, ref_date,
            neutral=neutral, home_team=home_team, model=req.model,
            squad_value_a=xi_val_a, squad_value_b=xi_val_b,
        )

    result = await loop.run_in_executor(executor, _run_predict)

    # Extraer campos según modo
    if req.knockout:
        pred = result["regulation"]
        p_penalties = float(result.get("p_penalties", 0))
        p_advance_a = float(result.get("p_advance_a", 0))
        p_advance_b = float(result.get("p_advance_b", 0))
    else:
        pred = result
        p_penalties = p_advance_a = p_advance_b = None

    p_a = float(pred.p_a)
    p_draw = float(pred.p_draw)
    p_b = float(pred.p_b)
    xg_a = float(pred.expected_goals_a)
    xg_b = float(pred.expected_goals_b)
    scorelines = pred.top_scorelines
    explanation = pred.explanation or {}
    trend_a = float(explanation.get("trend_a", 0))
    trend_b = float(explanation.get("trend_b", 0))

    narrative = _build_narrative(
        team_a, team_b, p_a, p_draw, p_b,
        xg_a, xg_b, scorelines, trend_a, trend_b, venue_label,
    )

    top_sc = [
        ScoreProbability(score_a=int(ga), score_b=int(gb), probability=float(p))
        for ga, gb, p in scorelines[:8]
    ]

    return PredictResponse(
        team_a=team_a,
        team_b=team_b,
        team_a_es=TEAM_EN_TO_ES.get(team_a, team_a),
        team_b_es=TEAM_EN_TO_ES.get(team_b, team_b),
        flag_a=flag(team_a),
        flag_b=flag(team_b),
        p_a=p_a,
        p_draw=p_draw,
        p_b=p_b,
        xg_a=xg_a,
        xg_b=xg_b,
        top_scorelines=top_sc,
        neutral=neutral,
        home_team=home_team,
        venue_label=venue_label,
        squad_desc_a=xi_desc_a,
        squad_desc_b=xi_desc_b,
        narrative=narrative,
        is_knockout=req.knockout,
        p_penalties=p_penalties,
        p_advance_a=p_advance_a,
        p_advance_b=p_advance_b,
    )
