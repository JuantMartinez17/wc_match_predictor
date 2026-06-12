"""
data/lineups.py
===============
11 inicial confirmado del Mundial 2026 vía SofaScore API.

Flujo:
  1. Obtiene el season_id del Mundial 2026 en SofaScore (caché 7 días).
  2. Busca el event_id del partido por fecha y equipos (caché 1 hora).
  3. Descarga el lineup del evento (caché 1 hora — se actualiza al anunciarse).

El lineup se anuncia típicamente 1 hora antes del pitido inicial.
Retorna None con mensaje claro si todavía no está disponible.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_BASE = "https://api.sofascore.com/api/v1"
_WC_TOURNAMENT_ID = 16  # FIFA World Cup en SofaScore

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

_TTL_SEASON = 7 * 24 * 3600  # 7 días  — el season_id no cambia
_TTL_EVENT = 3600  # 1 hora  — el event_id tampoco cambia
_TTL_LINEUP = 3600  # 1 hora  — re-chequea por si se actualizó


# Nombres de equipos tal como aparecen en SofaScore para el filtro de eventos
_SS_TEAM_NAME: dict[str, str] = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde",
    "Curaçao": "Curacao",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Turkey": "Türkiye",
}


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_").replace("'", "")


def _fresh(path: Path, ttl: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl


def _cache_dir_init(cache_dir: str | Path) -> Path:
    p = Path(cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Season ID del Mundial 2026
# ---------------------------------------------------------------------------


def _season_id_path(cache_dir: Path) -> Path:
    return cache_dir / "ss_wc2026_season_id.json"


def _get_wc2026_season_id(cache_dir: Path) -> int | None:
    path = _season_id_path(cache_dir)
    if _fresh(path, _TTL_SEASON):
        return json.loads(path.read_text(encoding="utf-8")).get("id")

    try:
        data = _fetch(f"{_BASE}/unique-tournament/{_WC_TOURNAMENT_ID}/seasons")
        seasons = data.get("seasons", [])
        # Buscar temporada 2026 (la más reciente con "2026" en el nombre o year)
        for s in seasons:
            name = str(s.get("name", ""))
            year = s.get("year", "")
            if "2026" in name or "2026" in str(year):
                sid = s["id"]
                path.write_text(json.dumps({"id": sid, "name": name}), encoding="utf-8")
                return sid
        # Fallback: la temporada más reciente
        if seasons:
            sid = seasons[0]["id"]
            path.write_text(json.dumps({"id": sid}), encoding="utf-8")
            return sid
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Búsqueda del evento (partido) por fecha y equipos
# ---------------------------------------------------------------------------


def _event_id_path(team_a: str, team_b: str, match_date: str, cache_dir: Path) -> Path:
    key = f"{_slug(team_a)}_vs_{_slug(team_b)}_{match_date}"
    return cache_dir / f"ss_event_{key}.json"


def _name_matches(ss_name: str, canonical: str) -> bool:
    """Compara nombre SofaScore con nombre canónico, tolerando variaciones."""
    import difflib

    ss_lower = ss_name.lower()
    canon_lower = canonical.lower()
    mapped_lower = _SS_TEAM_NAME.get(canonical, canonical).lower()
    if canon_lower in ss_lower or ss_lower in canon_lower:
        return True
    if mapped_lower in ss_lower or ss_lower in mapped_lower:
        return True
    return bool(
        difflib.get_close_matches(
            ss_lower, [canon_lower, mapped_lower], n=1, cutoff=0.75
        )
    )


def find_match_event_id(
    team_a: str,
    team_b: str,
    match_date: str,
    cache_dir: Path,
) -> int | None:
    """
    Busca el event_id del partido en SofaScore paginando los eventos
    próximos y recientes del torneo, filtrando por fecha y equipos.

    SofaScore no expone un endpoint por fecha; se usan los segmentos
    `next/{page}` y `last/{page}` (10 eventos por página) y se filtra
    por timestamp dentro del día UTC del partido.
    """
    path = _event_id_path(team_a, team_b, match_date, cache_dir)
    if _fresh(path, _TTL_EVENT):
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached.get("event_id")

    season_id = _get_wc2026_season_id(cache_dir)
    if not season_id:
        return None

    # Ventana de timestamp para el día UTC de match_date
    try:
        import datetime as _dt

        day_start = int(
            _dt.datetime.strptime(match_date, "%Y-%m-%d")
            .replace(tzinfo=_dt.UTC)
            .timestamp()
        )
    except Exception:
        day_start = 0
    day_end = day_start + 86400

    # Paginar next y last (3 páginas × 10 eventos × 2 segmentos = 60 eventos)
    for segment in ("next", "last"):
        for page in range(3):
            try:
                data = _fetch(
                    f"{_BASE}/unique-tournament/{_WC_TOURNAMENT_ID}"
                    f"/season/{season_id}/events/{segment}/{page}"
                )
                events = data.get("events", [])
                if not events:
                    break  # sin más páginas

                for evt in events:
                    ts = evt.get("startTimestamp", 0)
                    if not (day_start <= ts < day_end):
                        continue
                    ht = evt.get("homeTeam", {}).get("name", "")
                    at = evt.get("awayTeam", {}).get("name", "")
                    if _name_matches(ht, team_a) and _name_matches(at, team_b):
                        eid = evt["id"]
                        path.write_text(json.dumps({"event_id": eid}), encoding="utf-8")
                        return eid
                    if _name_matches(ht, team_b) and _name_matches(at, team_a):
                        eid = evt["id"]
                        path.write_text(
                            json.dumps({"event_id": eid, "swapped": True}),
                            encoding="utf-8",
                        )
                        return eid
            except Exception:
                break

    return None


# ---------------------------------------------------------------------------
# Lineup del partido
# ---------------------------------------------------------------------------


def _lineup_path(team_a: str, team_b: str, match_date: str, cache_dir: Path) -> Path:
    key = f"{_slug(team_a)}_vs_{_slug(team_b)}_{match_date}"
    return cache_dir / f"lineup_{key}.json"


def get_lineup(
    team_a: str,
    team_b: str,
    match_date: str,
    cache_dir: str | Path = "data/cache",
) -> dict[str, list[str]] | None:
    """
    Obtiene el 11 inicial confirmado de ambos equipos.

    Returns
    -------
    {"team_a": [nombres], "team_b": [nombres]} si el lineup está disponible.
    None si no está confirmado todavía o si no se pudo obtener.

    Los nombres retornados son los que usa SofaScore (pueden diferir
    levemente de Transfermarkt — se usa fuzzy matching en players.py).
    """
    cache_dir = _cache_dir_init(cache_dir)
    lineup_path = _lineup_path(team_a, team_b, match_date, cache_dir)

    if _fresh(lineup_path, _TTL_LINEUP):
        cached = json.loads(lineup_path.read_text(encoding="utf-8"))
        if cached.get("confirmed"):
            return {"team_a": cached["team_a"], "team_b": cached["team_b"]}
        return None

    event_id = find_match_event_id(team_a, team_b, match_date, cache_dir)
    if not event_id:
        return None

    try:
        data = _fetch(f"{_BASE}/event/{event_id}/lineups")

        # Verificar si el lineup está confirmado
        confirmed = data.get("confirmed", False)
        if not confirmed:
            # Guardar estado "no confirmado" para evitar requests repetidos
            lineup_path.write_text(json.dumps({"confirmed": False}), encoding="utf-8")
            return None

        # Determinar si los equipos están invertidos respecto al evento
        event_path = _event_id_path(team_a, team_b, match_date, cache_dir)
        swapped = False
        if event_path.exists():
            swapped = json.loads(event_path.read_text(encoding="utf-8")).get(
                "swapped", False
            )

        home_players = _extract_starters(data.get("home", {}))
        away_players = _extract_starters(data.get("away", {}))

        if swapped:
            players_a, players_b = away_players, home_players
        else:
            players_a, players_b = home_players, away_players

        result = {"confirmed": True, "team_a": players_a, "team_b": players_b}
        lineup_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return {"team_a": players_a, "team_b": players_b}

    except Exception:
        return None


def _extract_starters(side: dict) -> list[str]:
    """Extrae los nombres de los titulares (substitute=False) del lado del lineup."""
    starters = []
    for entry in side.get("players", []):
        if not entry.get("substitute", True):
            name = entry.get("player", {}).get("name", "")
            if name:
                starters.append(name)
    return starters


# ---------------------------------------------------------------------------
# CLI: python -m data.lineups "Argentina" "France" 2026-06-15
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if len(args) < 3:
        print('Uso: python -m data.lineups "Equipo A" "Equipo B" YYYY-MM-DD')
        sys.exit(1)

    ta, tb, fecha = args[0], args[1], args[2]
    print(f"Buscando lineup: {ta} vs {tb}  [{fecha}]")
    lineup = get_lineup(ta, tb, fecha)
    if lineup is None:
        print("  Lineup no disponible todavia (se anuncia ~1h antes del partido).")
    else:
        print(f"  {ta}: {', '.join(lineup['team_a'])}")
        print(f"  {tb}: {', '.join(lineup['team_b'])}")
