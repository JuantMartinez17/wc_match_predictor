"""
data/fixture.py
===============
Fixture oficial del Mundial 2026 vía ESPN API pública (sin autenticación).

Endpoint: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard
Retorna partidos del día con estado, equipos y marcador si ya se jugó.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

_ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
    "fifa.world/scoreboard?dates={date}&limit=20"
)
# Consulta por RANGO de fechas: trae todo el torneo en una sola llamada.
_ESPN_URL_RANGE = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
    "fifa.world/scoreboard?dates={start}-{end}&limit=200"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
_CACHE_TTL = 1800  # 30 minutos — el fixture cambia poco pero el estado (live) sí
_CACHE_TTL_PAST = 86400  # 24 h — los partidos de días pasados ya están finalizados
WC_START = date(2026, 6, 11)  # primer día del Mundial 2026; no se consulta antes
# Margen de días desde WC_START para cubrir todo el torneo (hasta la final, ~07-19).
WC_HORIZON_DAYS = 45
_TOURNAMENT_CACHE = "fixture_tournament.json"


# Mapa de nombres ESPN → nombres canónicos del proyecto
_ESPN_TO_CANONICAL: dict[str, str] = {
    "United States": "USA",
    "South Korea": "Korea Republic",
    "DR Congo": "Congo DR",
    "Ivory Coast": "Côte d'Ivoire",
    "Cape Verde": "Cabo Verde",
    "Curacao": "Curaçao",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Türkiye": "Turkey",
    "Turkey": "Turkey",
    "IR Iran": "Iran",
}

# Estados de partido ESPN → etiqueta legible
_STATUS_LABEL: dict[str, str] = {
    "STATUS_SCHEDULED": "programado",
    "STATUS_IN_PROGRESS": "en juego",
    "STATUS_HALFTIME": "descanso",
    "STATUS_FINAL": "finalizado",
    "STATUS_POSTPONED": "postergado",
    "STATUS_CANCELED": "cancelado",
    "STATUS_SUSPENDED": "suspendido",
    "STATUS_FULL_TIME": "finalizado"
}


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def _canonical(name: str) -> str:
    return _ESPN_TO_CANONICAL.get(name, name)


def _cache_path(d: date, cache_dir: Path) -> Path:
    return cache_dir / f"fixture_{d.isoformat()}.json"


def _is_fresh(path: Path, ttl: float = _CACHE_TTL) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl


def _parse_events(data: dict) -> list[dict]:
    matches = []
    for event in data.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        # ESPN pone al "home" primero, pero en torneos neutrales puede variar
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        team_a = _canonical(home.get("team", {}).get("displayName", ""))
        team_b = _canonical(away.get("team", {}).get("displayName", ""))
        if not team_a or not team_b:
            continue

        status_key = comp.get("status", {}).get("type", {}).get("name", "")
        status = _STATUS_LABEL.get(status_key, status_key)

        score_a = home.get("score", "")
        score_b = away.get("score", "")

        # Fecha y hora en ISO
        event_date_str = event.get("date", "")  # "2026-06-11T20:00Z"

        # Extraer solo la parte de la fecha para agrupar
        if "T" in event_date_str:
            date_part, time_part = event_date_str.split("T")
            time_part = time_part.replace("Z", "")[:5]
        else:
            date_part = event_date_str
            time_part = ""

        matches.append({
            "id": event.get("id", ""),
            "date": date_part,          # "2026-06-11"
            "time_utc": time_part,      # "20:00"
            "team_a": team_a,
            "team_b": team_b,
            "status": status,
            "score_a": score_a,
            "score_b": score_b,
            "neutral": comp.get("neutralSite", True),
            "round": event.get("season", {}).get("slug", ""),
            "venue": comp.get("venue", {}).get("fullName", ""),
        })
    return matches


def _load_day(d: date, cache_dir: Path, today: date) -> list[dict]:
    """
    Carga los partidos de UN día (caché o ESPN). Núcleo reutilizable por
    `get_fixture` (rango) y `get_fixture_by_date` (un solo día).

    - No consulta días previos al inicio del Mundial (ESPN no devolvería nada;
      serían llamadas HTTP desperdiciadas).
    - Días pasados usan TTL largo (ya finalizados, no cambian); hoy/futuro 30 min.
    - Sin conexión: usa caché aunque sea viejo; si no hay nada, lista vacía.
    """
    if d < WC_START:
        return []
    path = _cache_path(d, cache_dir)
    ttl = _CACHE_TTL_PAST if d < today else _CACHE_TTL
    if _is_fresh(path, ttl):
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        data = _fetch(_ESPN_URL.format(date=d.strftime("%Y%m%d")))
        day_matches = _parse_events(data)
        path.write_text(json.dumps(day_matches, ensure_ascii=False), encoding="utf-8")
        return day_matches
    except (urllib.error.URLError, Exception):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []


def get_fixture(
    days_ahead: int = 7,
    include_past_days: int = 1,
    cache_dir: str | Path = "data/cache",
) -> list[dict]:
    """
    Devuelve los partidos del Mundial en la ventana [hoy - past_days, hoy + days_ahead].

    Cada partido es un dict con:
        id, date, time_utc, team_a, team_b, status,
        score_a, score_b, neutral, round, venue.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    all_matches: list[dict] = []
    for delta in range(-include_past_days, days_ahead + 1):
        all_matches.extend(_load_day(today + timedelta(days=delta), cache_dir, today))

    # Ordenar por fecha y hora
    return sorted(all_matches, key=lambda m: (m["date"], m["time_utc"]))


def get_tournament_fixture(cache_dir: str | Path = "data/cache") -> list[dict]:
    """
    Devuelve TODOS los partidos del torneo en UNA sola llamada a ESPN (consulta por
    rango de fechas), cacheada. Es la base para filtrar por instancia/jornada sin
    recorrer día por día.

    Cada match incluye el campo `round` con el slug de ESPN, que distingue las
    rondas de eliminatoria: `group-stage`, `round-of-32`, `round-of-16`,
    `quarterfinals`, `semifinals`, `3rd-place-match`, `final`. (La fase de grupos no
    trae la jornada/fecha; se deriva en data/instances.py.)

    Caché 30 min. Sin conexión: usa la última versión cacheada (aunque sea vieja).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / _TOURNAMENT_CACHE
    if _is_fresh(path, _CACHE_TTL):
        return json.loads(path.read_text(encoding="utf-8"))

    start = WC_START.strftime("%Y%m%d")
    end = (WC_START + timedelta(days=WC_HORIZON_DAYS)).strftime("%Y%m%d")
    try:
        data = _fetch(_ESPN_URL_RANGE.format(start=start, end=end))
        matches = _parse_events(data)
        path.write_text(json.dumps(matches, ensure_ascii=False), encoding="utf-8")
        return matches
    except (urllib.error.URLError, Exception):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []


if __name__ == "__main__":
    fixture = get_fixture(days_ahead=7)
    if not fixture:
        print("No se pudo obtener el fixture.")
    else:
        print(f"Partidos encontrados: {len(fixture)}\n")
        current_date = ""
        for m in fixture:
            if m["date"] != current_date:
                current_date = m["date"]
                print(f"\n--- {current_date} ---")
            status_str = f"  [{m['score_a']}-{m['score_b']}]" if m["status"] == "finalizado" else f"  {m['time_utc']} UTC"
            print(f"  {m['team_a']:25} vs {m['team_b']:25}{status_str}")
