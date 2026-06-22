"""
data/lineups.py
===============
11 inicial confirmado del Mundial 2026 vía ESPN API pública (sin autenticación).

Flujo:
  1. Busca el event_id en el scoreboard de ESPN por fecha y equipos (caché 24 h).
  2. Descarga el summary del evento que incluye el roster completo.
     - Si el lineup no está confirmado: caché 3 min (re-chequea frecuente).
     - Si está confirmado: caché 12 h (no necesita re-fetch).

El lineup se anuncia típicamente ~1 hora antes del pitido inicial y sigue
disponible durante el partido y una vez finalizado. Para partidos ya empezados
(estado ESPN "in"/"post") no se confía en el caché negativo: el 11 ya existe,
así que se reintenta hasta obtenerlo.
Retorna None si todavía no está disponible o si el partido no fue encontrado.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, timedelta
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

_TTL_EVENT      = 86400  # 24 h — el event_id no cambia una vez encontrado
_TTL_EVENT_MISS =  1800  # 30 min — un "no encontrado" se reintenta pronto (no 24 h)
_TTL_PENDING    =   180  # 3 min — pre-partido: re-chequea hasta que lo anuncien
_TTL_LIVE_RETRY =    60  # 1 min — partido ya empezado sin lineup: reintenta seguido
_TTL_CONFIRMED  = 43200  # 12 h — innecesario re-fetch una vez confirmado

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


def _scan_scoreboard(data: dict, team_a: str, team_b: str) -> tuple[int, bool] | None:
    """Busca (event_id, swapped) del partido en un scoreboard ESPN, o None."""
    for event in data.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        competitors = comps[0].get("competitors", [])
        if len(competitors) < 2:
            continue

        team_h = next(
            (c for c in competitors if c.get("homeAway") == "home"), competitors[0]
        )
        team_aw = next(
            (c for c in competitors if c.get("homeAway") == "away"), competitors[1]
        )
        espn_home = team_h.get("team", {}).get("displayName", "")
        espn_away = team_aw.get("team", {}).get("displayName", "")
        eid = int(event["id"])

        if _names_match(espn_home, team_a) and _names_match(espn_away, team_b):
            return eid, False
        if _names_match(espn_home, team_b) and _names_match(espn_away, team_a):
            return eid, True
    return None


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
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        eid = cached.get("event_id")
        if eid and _fresh(path, _TTL_EVENT):
            return eid, cached.get("swapped", False)
        # Un "no encontrado" sólo se respeta un rato corto: pudo ser transitorio
        # (el partido aparece más tarde, o el bucket de fecha cambió).
        if not eid and _fresh(path, _TTL_EVENT_MISS):
            return None, None
        # Caché vencida → re-buscar

    # ESPN agrupa los partidos por una fecha que puede diferir ±1 día de la fecha
    # UTC del evento (timezone): un partido a las 01:00Z del 14 cae en el bucket
    # del 13. Se busca en la fecha y sus vecinas para no perderlo.
    try:
        base = date.fromisoformat(match_date)
        dates = [
            d.strftime("%Y%m%d")
            for d in (base, base - timedelta(days=1), base + timedelta(days=1))
        ]
    except (ValueError, TypeError):
        dates = [match_date.replace("-", "")]

    for ds in dates:
        try:
            data = _fetch(_ESPN_SCOREBOARD.format(date=ds))
        except Exception:
            continue
        found = _scan_scoreboard(data, team_a, team_b)
        if found is not None:
            eid, swapped = found
            path.write_text(
                json.dumps({"event_id": eid, "swapped": swapped}), encoding="utf-8"
            )
            return eid, swapped

    path.write_text(json.dumps({"event_id": None}), encoding="utf-8")
    return None, None


# ---------------------------------------------------------------------------
# Paso 2 — Extraer el 11 inicial del summary del evento
# ---------------------------------------------------------------------------


def _lineup_cache_path(event_id: int, cache_dir: Path) -> Path:
    return cache_dir / f"espn_lineup_{event_id}.json"


def _event_state(summary: dict) -> str:
    """
    Estado del partido ('pre' | 'in' | 'post') leído del summary de ESPN.
    Se usa para decidir si confiar en el caché negativo: un partido ya empezado
    ('in'/'post') tiene el 11 publicado, así que conviene reintentar.
    """
    try:
        comps = summary.get("header", {}).get("competitions", [])
        return comps[0].get("status", {}).get("type", {}).get("state", "") or ""
    except Exception:
        return ""


def _extract_starters(roster: list[dict]) -> list[str]:
    """
    Nombres del 11 inicial de un roster ESPN.

    Prioriza la marca `starter=True`. Si ESPN no la setea (varía entre pre-partido,
    en vivo y finalizado) pero asignó posición de formación al XI
    (`formationPlace` distinto de vacío/'0'), cae a ese criterio. Así el lineup
    se extrae igual con un partido en curso.
    """
    strict = [
        entry.get("athlete", {}).get("fullName", "")
        for entry in roster
        if entry.get("starter") is True and entry.get("athlete", {}).get("fullName")
    ]
    if len(strict) >= 7:
        return strict

    lenient = [
        entry.get("athlete", {}).get("fullName", "")
        for entry in roster
        if str(entry.get("formationPlace", "") or "") not in ("", "0")
        and entry.get("athlete", {}).get("fullName")
    ]
    return lenient if len(lenient) >= 7 else strict


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_lineup(roster: list[dict]) -> list[dict]:
    """
    11 inicial con detalle por jugador para dibujar la cancha:
    [{"name", "jersey", "position", "formation_place"}], ordenado por slot.

    Usa la misma detección de titular que `_extract_starters` (flag `starter`,
    con fallback a `formationPlace != 0`). `position` es la abreviatura ESPN
    (G, RB, CB, CM-R, LM, CF-L, …).
    """
    def _named(entries: list[dict]) -> list[dict]:
        return [e for e in entries if e.get("athlete", {}).get("fullName")]

    strict = _named([e for e in roster if e.get("starter") is True])
    if len(strict) >= 7:
        chosen = strict
    else:
        lenient = _named(
            [
                e
                for e in roster
                if str(e.get("formationPlace", "") or "") not in ("", "0")
            ]
        )
        chosen = lenient if len(lenient) >= 7 else strict

    slots = [
        {
            "name": e.get("athlete", {}).get("fullName", ""),
            "jersey": _to_int(e.get("jersey")),
            "position": (e.get("position") or {}).get("abbreviation"),
            "formation_place": _to_int(e.get("formationPlace")),
        }
        for e in chosen
    ]
    # Ordenar por slot (1 = arquero … 11); los sin slot quedan al final.
    slots.sort(key=lambda s: (s["formation_place"] is None, s["formation_place"] or 0))
    return slots


def _fetch_lineup_from_summary(
    event_id: int,
    swapped: bool,
    team_a: str,
    team_b: str,
    cache_dir: Path,
) -> dict | None:
    """
    Llama a ESPN summary y extrae los 11 iniciales con formación y detalle.

    Devuelve, o None si no está disponible:
        {"team_a": [nombres], "team_b": [nombres],
         "formation_a": "4-4-2", "formation_b": "4-3-3",
         "detail_a": [{name, jersey, position, formation_place}], "detail_b": [...]}
    """
    path = _lineup_cache_path(event_id, cache_dir)

    def _payload(src: dict) -> dict:
        # Lectura defensiva con .get(): cachés viejos (solo nombres) → formación
        # y detalle None hasta que el caché se refresque.
        return {
            "team_a": src["team_a"],
            "team_b": src["team_b"],
            "formation_a": src.get("formation_a"),
            "formation_b": src.get("formation_b"),
            "detail_a": src.get("detail_a"),
            "detail_b": src.get("detail_b"),
        }

    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("confirmed") and _fresh(path, _TTL_CONFIRMED):
            return _payload(cached)
        if not cached.get("confirmed"):
            # Caché negativo. Para un partido ya empezado ('in'/'post') el 11 ya
            # existe: se reintenta con un piso corto (no se respeta el TTL largo
            # de pre-partido), así un partido en curso no queda pegado en null.
            started = cached.get("state") in ("in", "post")
            ttl = _TTL_LIVE_RETRY if started else _TTL_PENDING
            if _fresh(path, ttl):
                return None
        # Confirmado expirado o negativo vencido → re-fetch a continuación

    try:
        data = _fetch(_ESPN_SUMMARY.format(event_id=event_id))
    except Exception:
        return None

    state = _event_state(data)  # 'pre' | 'in' | 'post' — guía el caché negativo

    home_side, away_side = {}, {}
    for side in data.get("rosters", []):
        if side.get("homeAway") == "home":
            home_side = side
        elif side.get("homeAway") == "away":
            away_side = side

    home_starters = _extract_starters(home_side.get("roster", []))
    away_starters = _extract_starters(away_side.get("roster", []))

    if len(home_starters) < 7 or len(away_starters) < 7:
        # Sin 11 completo todavía. Se guarda el estado para que, si el partido
        # ya empezó, la próxima llamada reintente con el piso corto.
        path.write_text(
            json.dumps({"confirmed": False, "state": state}), encoding="utf-8"
        )
        return None

    home = {
        "names": home_starters,
        "formation": home_side.get("formation"),
        "detail": _extract_lineup(home_side.get("roster", [])),
    }
    away = {
        "names": away_starters,
        "formation": away_side.get("formation"),
        "detail": _extract_lineup(away_side.get("roster", [])),
    }
    a, b = (away, home) if swapped else (home, away)

    result = {
        "confirmed": True,
        "state": state,
        "team_a": a["names"],
        "team_b": b["names"],
        "formation_a": a["formation"],
        "formation_b": b["formation"],
        "detail_a": a["detail"],
        "detail_b": b["detail"],
    }
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return _payload(result)


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def get_lineup(
    team_a: str,
    team_b: str,
    match_date: str,
    cache_dir: str | Path = "data/cache",
) -> dict | None:
    """
    Obtiene el 11 inicial confirmado de ambos equipos vía ESPN API.

    Parameters
    ----------
    team_a, team_b : nombres canónicos del proyecto (ej. "Argentina").
    match_date     : fecha del partido en formato "YYYY-MM-DD".
    cache_dir      : directorio de caché local.

    Returns
    -------
    dict con el lineup, o None si no está confirmado todavía:
        {"team_a": [nombres], "team_b": [nombres],
         "formation_a": "4-4-2"|None, "formation_b": ...,
         "detail_a": [{name, jersey, position, formation_place}], "detail_b": [...]}
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
