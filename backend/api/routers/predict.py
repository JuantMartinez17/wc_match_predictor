"""
backend/api/routers/predict.py
==============================
POST /api/predict — predicción de un partido del Mundial 2026.

El request recibe IDs de equipos (slugs de /api/teams), no texto libre.
La resolución canónica es un lookup O(1) sin fuzzy matching.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

from ..constants import CANONICAL_BY_ID, flag, team_id
from ..schemas import PredictRequest, PredictResponse, ScoreProbability

router = APIRouter()


# ---------------------------------------------------------------------------
# Caché de respuestas (TTL corto: debe captar la confirmación del lineup,
# que aparece ~1 h antes del pitido y cambia la predicción)
# ---------------------------------------------------------------------------

_RESPONSE_CACHE: OrderedDict[tuple, tuple[float, PredictResponse]] = OrderedDict()
# TTL corto para partidos de hoy/mañana: el lineup puede confirmarse (~1 h antes)
# y cambiar la predicción. TTL largo para futuros: nada cambia hasta esa ventana.
_RESPONSE_TTL = 120.0  # segundos
_RESPONSE_TTL_FAR = 1800.0  # segundos (partidos a >1 día)
_RESPONSE_MAX = 256
_response_lock = threading.Lock()


def _cache_get(key: tuple) -> PredictResponse | None:
    with _response_lock:
        entry = _RESPONSE_CACHE.get(key)
        if entry is None:
            return None
        expires, resp = entry
        if time.monotonic() >= expires:
            del _RESPONSE_CACHE[key]
            return None
        _RESPONSE_CACHE.move_to_end(key)
        return resp


def _cache_put(key: tuple, resp: PredictResponse, ttl: float = _RESPONSE_TTL) -> None:
    with _response_lock:
        _RESPONSE_CACHE[key] = (time.monotonic() + ttl, resp)
        _RESPONSE_CACHE.move_to_end(key)
        while len(_RESPONSE_CACHE) > _RESPONSE_MAX:
            _RESPONSE_CACHE.popitem(last=False)


# ---------------------------------------------------------------------------
# Narrativa en lenguaje simple
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

    if p_a >= 0.62:
        partes.append(f"{nombre_a} llega como gran favorito ante {nombre_b}.")
    elif p_b >= 0.62:
        partes.append(f"{nombre_b} llega como gran favorito ante {nombre_a}.")
    elif p_a >= 0.50:
        partes.append(
            f"{nombre_a} tiene una leve ventaja, pero el partido está abierto."
        )
    elif p_b >= 0.50:
        partes.append(
            f"{nombre_b} tiene una leve ventaja, pero el partido está abierto."
        )
    else:
        partes.append(f"Partido muy parejo entre {nombre_a} y {nombre_b}.")

    if "sede" in venue_label.lower():
        partes.append("Además, juega con el apoyo de su hinchada.")

    total = xg_a + xg_b
    if total < 1.9:
        partes.append("Se espera un partido cerrado, con pocos goles.")
    elif total < 2.7:
        partes.append("Se anticipan entre 2 y 3 goles en total.")
    else:
        partes.append("Hay chances de que sea un partido con varios goles.")

    if top_scorelines:
        ga, gb, p_top = top_scorelines[0]
        if ga == gb:
            partes.append(
                f"El resultado más probable es un empate {ga}-{gb} ({p_top * 100:.0f}% de chances)."
            )
        elif ga > gb:
            partes.append(
                f"El marcador más probable es {ga}-{gb} a favor de {nombre_a} ({p_top * 100:.0f}% de chances)."
            )
        else:
            partes.append(
                f"El marcador más probable es {gb}-{ga} a favor de {nombre_b} ({p_top * 100:.0f}% de chances)."
            )

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


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Predecir resultado de un partido",
    response_description="Probabilidades 1X2, goles esperados, marcadores más probables y narrativa en español.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "Fase de grupos": {
                            "summary": "Argentina vs Alemania — fase de grupos",
                            "value": {
                                "team_a_id": 2,
                                "team_b_id": 19,
                                "date": "2026-06-28",
                                "knockout": False,
                                "model": "dixon_coles",
                            },
                        },
                        "Eliminatoria": {
                            "summary": "Argentina vs Francia — cuartos de final (con prórroga y penales)",
                            "value": {
                                "team_a_id": 2,
                                "team_b_id": 18,
                                "date": "2026-07-04",
                                "knockout": True,
                                "model": "dixon_coles",
                            },
                        },
                        "Modelo alternativo": {
                            "summary": "Brasil vs España — usando Poisson bivariado",
                            "value": {
                                "team_a_id": 7,
                                "team_b_id": 41,
                                "date": "2026-06-30",
                                "knockout": False,
                                "model": "bivariate_poisson",
                            },
                        },
                    }
                }
            }
        }
    },
)
async def predict_match(req: PredictRequest, request: Request) -> PredictResponse:
    """
    Corre el motor de predicción completo para un partido y devuelve el resultado.

    ### Motor de predicción
    1. **Elo** — rating histórico de cada selección con decay temporal.
    2. **GLM de fuerza** — ataque/defensa ajustados por rival con shrinkage hacia prior Elo.
    3. **Modelo de marcador** — Dixon-Coles (por defecto), Poisson Bivariado o Poisson Simple.
    4. **Probabilidades exactas** — cálculo determinista sobre la matriz conjunta
       de marcadores → probabilidades 1X2 calibradas.
    5. **Ajustes secundarios** — valor del XI (Transfermarkt), disponibilidad de jugadores
       (penaliza ausencias de titulares clave cuando el lineup está confirmado),
       historial directo y factor entrenador.

    ### Lineup confirmado
    Cuando el 11 inicial está disponible en SofaScore (≈1 h antes del pitido),
    el motor usa el valor real de los titulares y penaliza la ausencia de jugadores
    clave del top-15 por valor de mercado (probable lesión o suspensión en el contexto
    del Mundial).

    ### Errores
    - `422` — ID de equipo inválido, ambos equipos iguales, o body mal formado.
    - `503` — El predictor aún está cargando (primera petición tras arrancar).
    """
    predictor = request.app.state.predictor
    executor = request.app.state.executor
    loop = asyncio.get_running_loop()

    # Resolver IDs → nombres canónicos (O(1), sin fuzzy matching)
    team_a = CANONICAL_BY_ID.get(req.team_a_id)
    team_b = CANONICAL_BY_ID.get(req.team_b_id)

    if team_a is None:
        raise HTTPException(
            status_code=422,
            detail=f"ID de equipo inválido: '{req.team_a_id}'. Consultá /api/teams para ver los IDs válidos.",
        )
    if team_b is None:
        raise HTTPException(
            status_code=422,
            detail=f"ID de equipo inválido: '{req.team_b_id}'. Consultá /api/teams para ver los IDs válidos.",
        )
    if team_a == team_b:
        raise HTTPException(
            status_code=422, detail="Los dos equipos deben ser distintos."
        )

    ref_date = req.date or str(date.today())

    # Caché de respuestas: requests idénticos dentro del TTL responden directo.
    cache_key = (req.team_a_id, req.team_b_id, ref_date, req.model, req.knockout)
    cached_resp = _cache_get(cache_key)
    if cached_resp is not None:
        return cached_resp

    # Venue
    from predict import TEAM_EN_TO_ES, _resolve_xi_value, detect_venue

    neutral, home_team = detect_venue(team_a, team_b)
    home_team_id = team_id(home_team) if home_team else None
    venue_label = (
        f"Local: {TEAM_EN_TO_ES.get(home_team, home_team)} (sede del Mundial)"
        if not neutral and home_team
        else "Cancha neutral"
    )

    # Squad values: lookup local cacheado (lru_cache sobre JSON de ratings),
    # del orden de microsegundos — no justifica el costo de despachar a un
    # thread. Solo el lineup (HTTP a ESPN) va al pool; para fechas lejanas
    # _fetch_lineup corta sin red (ver predict.py), dejando el request en CPU.
    from predict import _fetch_lineup, _fetch_squad_values

    squad_a = _fetch_squad_values(team_a)
    squad_b = _fetch_squad_values(team_b)
    lineup = await loop.run_in_executor(
        executor, _fetch_lineup, team_a, team_b, ref_date
    )

    lineup_a = lineup["team_a"] if lineup else None
    lineup_b = lineup["team_b"] if lineup else None
    xi_val_a, xi_desc_a = _resolve_xi_value(team_a, lineup_a, squad_a)
    xi_val_b, xi_desc_b = _resolve_xi_value(team_b, lineup_b, squad_b)

    from predict import _derive_absences

    absences_a = _derive_absences(lineup_a, squad_a)
    absences_b = _derive_absences(lineup_b, squad_b)

    # Lineup confirmado = se obtuvo el 11 inicial de ESPN, independiente de si
    # se pudo calcular el valor XI (que requiere squad values de SofaScore).
    lineup_confirmed_a = lineup_a is not None
    lineup_confirmed_b = lineup_b is not None

    # Predicción (CPU-bound → thread pool)
    def _run_predict():
        if req.knockout:
            return predictor.predict_knockout(
                team_a,
                team_b,
                ref_date,
                neutral=neutral,
                home_team=home_team,
                model=req.model,
                squad_value_a=xi_val_a,
                squad_value_b=xi_val_b,
                absences_a=absences_a,
                absences_b=absences_b,
            )
        return predictor.predict(
            team_a,
            team_b,
            ref_date,
            neutral=neutral,
            home_team=home_team,
            model=req.model,
            squad_value_a=xi_val_a,
            squad_value_b=xi_val_b,
            absences_a=absences_a,
            absences_b=absences_b,
            # Cálculo exacto sobre la matriz de marcadores: determinista y sin
            # el costo (~100-200 ms) ni el ruido de muestreo del Monte Carlo.
            use_simulation=False,
        )

    result = await loop.run_in_executor(executor, _run_predict)

    if req.knockout:
        pred = result["prediction"]
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
        team_a,
        team_b,
        p_a,
        p_draw,
        p_b,
        xg_a,
        xg_b,
        scorelines,
        trend_a,
        trend_b,
        venue_label,
    )

    top_sc = [
        ScoreProbability(score_a=int(ga), score_b=int(gb), probability=float(p))
        for ga, gb, p in scorelines[:8]
    ]

    response = PredictResponse(
        team_a_id=req.team_a_id,
        team_b_id=req.team_b_id,
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
        home_team_id=home_team_id,
        venue_label=venue_label,
        squad_desc_a=xi_desc_a,
        squad_desc_b=xi_desc_b,
        lineup_confirmed_a=lineup_confirmed_a,
        lineup_confirmed_b=lineup_confirmed_b,
        narrative=narrative,
        is_knockout=req.knockout,
        p_penalties=p_penalties,
        p_advance_a=p_advance_a,
        p_advance_b=p_advance_b,
    )
    # TTL adaptativo: corto si el partido es hoy/mañana (el lineup aún puede
    # confirmarse), largo si es futuro (la predicción no cambiará por un tiempo).
    try:
        far = date.fromisoformat(ref_date) > date.today() + timedelta(days=1)
    except (ValueError, TypeError):
        far = False
    _cache_put(cache_key, response, ttl=_RESPONSE_TTL_FAR if far else _RESPONSE_TTL)
    return response
