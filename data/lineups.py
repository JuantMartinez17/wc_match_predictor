"""
data/lineups.py
===============
11 inicial confirmado del Mundial 2026 vía ESPN API pública (sin autenticación).

Flujo:
  1. Busca el event_id en el scoreboard de ESPN por fecha y equipos (caché 24 h).
  2. Descarga el summary del evento que incluye el roster completo.
     - Si el lineup no está confirmado: caché 10 min (re-chequea frecuente).
     - Si está confirmado: caché 12 h (no necesita re-fetch).

El lineup se anuncia típicamente ~1 hora antes del pitido inicial.
Retorna None si todavía no está disponible o si el partido no fue encontrado.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

_ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
    "fifa.world/scoreboard?dates={date}&limit=20"
)
_ESPN_SUMMARY = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
    "fifa.world/summary?event={event_id}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_TTL_EVENT     = 86400  # 24 h — el event_id no cambia
_TTL_PENDING   =   600  # 10 min — re-chequea hasta que anuncien el lineup
_TTL_CONFIRMED = 43200  # 12 h — innecesario re-fetch una vez confirmado

# ESPN display name → nombre canónico del proyecto
_ESPN_TO_CANONICAL: dict[str, str] = {
    "United States": "USA",
    "South Korea":   "Korea Republic",
    "DR Congo":      "Congo DR",
    "Ivory Coast":   "Côte d'Ivoire",
    "Cape Verde":    "Cabo Verde",
    "Curacao":       "Curaçao",
    "Türkiye":       "Turkey",
    "Turkey":        "Turkey",
    "IR Iran":       "Iran",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina":   "Bosnia and Herzegovina",
    "Bosnia-Herzegovina":     "Bosnia and Herzegovina",
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


def _canonical(espn_name: str) -> str:
    return _ESPN_TO_CANONICAL.get(espn_name, espn_name)


def _names_match(espn_name: str, canonical: str) -> bool:
    """True si el nombre ESPN corresponde al nombre canónico del proyecto."""
    import difflib

    mapped = _canonical(espn_name)
    if mapped == canonical:
        return True
    return bool(
        difflib.get_close_matches(mapped.lower(), [canonical.lower()], n=1, cutoff=0.80)
    )


# ---------------------------------------------------------------------------
# Paso 1 — Obtener el ESPN event_id por fecha y equipos
# ---------------------------------------------------------------------------


def _event_cache_path(
    team_a: str, team_b: str, match_date: str, cache_dir: Path
) -> Path:
    key = f"{_slug(team_a)}_vs_{_slug(team_b)}_{match_date}"
    return cache_dir / f"espn_event_{key}.json"


def _find_espn_event_id(
    team_a: str,
    team_b: str,
    match_date: str,
    cache_dir: Path,
) -> tuple[int, bool] | tuple[None, None]:
    """
    Devuelve (event_id, swapped) donde swapped=True si ESPN tiene los equipos
    en orden inverso (home=team_b, away=team_a).
    Devuelve (None, None) si no se encontró el partido.
    """
    path = _event_cache_path(team_a, team_b, match_date, cache_dir)
    if _fresh(path, _TTL_EVENT):
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("event_id"):
            return cached["event_id"], cached.get("swapped", False)
        return None, None

    date_compact = match_date.replace("-", "")
    try:
        data = _fetch(_ESPN_SCOREBOARD.format(date=date_compact))
    except Exception:
        return None, None

    for event in data.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        team_h = next(
            (c for c in competitors if c.get("homeAway") == "home"), competitors[0]
        )
        team_a_comp = next(
            (c for c in competitors if c.get("homeAway") == "away"), competitors[1]
        )
        espn_home = team_h.get("team", {}).get("displayName", "")
        espn_away = team_a_comp.get("team", {}).get("displayName", "")

        eid = int(event["id"])

        if _names_match(espn_home, team_a) and _names_match(espn_away, team_b):
            path.write_text(
                json.dumps({"event_id": eid, "swapped": False}), encoding="utf-8"
            )
            return eid, False

        if _names_match(espn_home, team_b) and _names_match(espn_away, team_a):
            path.write_text(
                json.dumps({"event_id": eid, "swapped": True}), encoding="utf-8"
            )
            return eid, True

    path.write_text(json.dumps({"event_id": None}), encoding="utf-8")
    return None, None


# ---------------------------------------------------------------------------
# Paso 2 — Extraer el 11 inicial del summary del evento
# ---------------------------------------------------------------------------


def _lineup_cache_path(event_id: int, cache_dir: Path) -> Path:
    return cache_dir / f"espn_lineup_{event_id}.json"


def _extract_starters(roster: list[dict]) -> list[str]:
    return [
        entry.get("athlete", {}).get("fullName", "")
        for entry in roster
        if entry.get("starter") is True and entry.get("athlete", {}).get("fullName")
    ]


def _fetch_lineup_from_summary(
    event_id: int,
    swapped: bool,
    team_a: str,
    team_b: str,
    cache_dir: Path,
) -> dict[str, list[str]] | None:
    """
    Llama a ESPN summary y extrae los 11 iniciales.
    Devuelve {"team_a": [...], "team_b": [...]} o None si no está disponible.
    """
    path = _lineup_cache_path(event_id, cache_dir)

    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("confirmed") and _fresh(path, _TTL_CONFIRMED):
            return {"team_a": cached["team_a"], "team_b": cached["team_b"]}
        if not cached.get("confirmed") and _fresh(path, _TTL_PENDING):
            return None
        # Caché expirada: re-fetch a continuación

    try:
        data = _fetch(_ESPN_SUMMARY.format(event_id=event_id))
    except Exception:
        return None

    rosters = data.get("rosters", [])
    if not rosters:
        path.write_text(json.dumps({"confirmed": False}), encoding="utf-8")
        return None

    home_roster, away_roster = [], []
    for side in rosters:
        if side.get("homeAway") == "home":
            home_roster = side.get("roster", [])
        elif side.get("homeAway") == "away":
            away_roster = side.get("roster", [])

    home_starters = _extract_starters(home_roster)
    away_starters = _extract_starters(away_roster)

    if len(home_starters) < 7 or len(away_starters) < 7:
        path.write_text(json.dumps({"confirmed": False}), encoding="utf-8")
        return None

    if swapped:
        players_a, players_b = away_starters, home_starters
    else:
        players_a, players_b = home_starters, away_starters

    result = {"confirmed": True, "team_a": players_a, "team_b": players_b}
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return {"team_a": players_a, "team_b": players_b}


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def get_lineup(
    team_a: str,
    team_b: str,
    match_date: str,
    cache_dir: str | Path = "data/cache",
) -> dict[str, list[str]] | None:
    """
    Obtiene el 11 inicial confirmado de ambos equipos vía ESPN API.

    Parameters
    ----------
    team_a, team_b : nombres canónicos del proyecto (ej. "Argentina").
    match_date     : fecha del partido en formato "YYYY-MM-DD".
    cache_dir      : directorio de caché local.

    Returns
    -------
    {"team_a": [nombres], "team_b": [nombres]} si el lineup está disponible.
    None si no está confirmado todavía o no se pudo obtener.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    event_id, swapped = _find_espn_event_id(team_a, team_b, match_date, cache_dir)
    if event_id is None:
        return None

    return _fetch_lineup_from_summary(event_id, swapped, team_a, team_b, cache_dir)


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
    print(f"Buscando lineup ESPN: {ta} vs {tb}  [{fecha}]")
    lineup = get_lineup(ta, tb, fecha)
    if lineup is None:
        print("  Lineup no disponible todavía (se anuncia ~1h antes del partido).")
    else:
        print(f"  {ta}: {', '.join(lineup['team_a'])}")
        print(f"  {tb}: {', '.join(lineup['team_b'])}")
