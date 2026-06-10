"""
data/players.py
===============
Valores de mercado de jugadores por selección vía SofaScore API.
SofaScore expone los valores de Transfermarkt en sus perfiles de jugador.

Flujo:
  1. Busca el ID de la selección en SofaScore (caché 30 días).
  2. Descarga el roster del equipo (caché 7 días).
  3. Por cada jugador, obtiene su valor de mercado (caché 7 días).

Todo cae en fallback vacío si SofaScore no responde: el predictor
usará el valor de plantilla sintético como siempre.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_BASE = "https://api.sofascore.com/api/v1"
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

_TTL_TEAM_ID = 30 * 24 * 3600   # 30 días — IDs son estables
_TTL_SQUAD   =  7 * 24 * 3600   # 7 días  — valores cambian poco


# Nombres de búsqueda en SofaScore para los casos que difieren del canónico
_SEARCH_NAME: dict[str, str] = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde",
    "Curaçao": "Curacao",
    "Bosnia and Herzegovina": "Bosnia",
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


# ---------------------------------------------------------------------------
# Búsqueda de ID de selección
# ---------------------------------------------------------------------------

def _team_id_path(team: str, cache_dir: Path) -> Path:
    return cache_dir / f"ss_teamid_{_slug(team)}.json"


def find_national_team_id(team_canonical: str, cache_dir: Path) -> int | None:
    """
    Devuelve el ID de la selección en SofaScore, con caché de 30 días.
    Usa búsqueda por nombre; filtra por tipo 'national'.
    """
    path = _team_id_path(team_canonical, cache_dir)
    if _fresh(path, _TTL_TEAM_ID):
        return json.loads(path.read_text(encoding="utf-8")).get("id")

    query = _SEARCH_NAME.get(team_canonical, team_canonical)
    try:
        data = _fetch(f"{_BASE}/search/all?q={urllib.parse.quote(query)}")
        hits = data.get("teams", {}).get("hits", [])
        for hit in hits:
            team = hit.get("entity", {})
            if team.get("sport", {}).get("slug") != "football":
                continue
            # Las selecciones nacionales tienen type "national"
            if team.get("type") == "national":
                tid = team["id"]
                path.write_text(json.dumps({"id": tid, "name": team.get("name")}), encoding="utf-8")
                return tid
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Valores de mercado del plantel
# ---------------------------------------------------------------------------

def _squad_path(team: str, cache_dir: Path) -> Path:
    return cache_dir / f"squad_values_{_slug(team)}.json"


def get_squad_values(
    team_canonical: str,
    cache_dir: str | Path = "data/cache",
    force_refresh: bool = False,
) -> dict[str, float]:
    """
    Devuelve {nombre_jugador: valor_mercado_M_EUR} para el plantel completo.

    Usa SofaScore /team/{id}/players — cada jugador tiene `transfermarktValue`
    en euros. Retorna dict vacío si no hay datos disponibles.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    path = _squad_path(team_canonical, cache_dir)
    if not force_refresh and _fresh(path, _TTL_SQUAD):
        return json.loads(path.read_text(encoding="utf-8"))

    team_id = find_national_team_id(team_canonical, cache_dir)
    if not team_id:
        return {}

    try:
        data = _fetch(f"{_BASE}/team/{team_id}/players")
        result: dict[str, float] = {}
        for entry in data.get("players", []):
            player = entry.get("player", {})
            name = player.get("name", "").strip()
            value_eur = player.get("transfermarktValue") or 0
            if name and value_eur > 0:
                result[name] = round(value_eur / 1_000_000, 2)
        if result:
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Cálculo del valor del 11 inicial
# ---------------------------------------------------------------------------

def compute_xi_value(
    lineup_names: list[str],
    squad_values: dict[str, float],
) -> float | None:
    """
    Suma los valores de mercado de los jugadores del 11 inicial.

    Usa fuzzy matching para tolerar diferencias leves en nombres
    (transliteraciones, abreviaturas, etc.).
    Retorna None si no se pudo calcular (< 7 jugadores identificados).
    """
    import difflib

    found: list[float] = []
    squad_names = list(squad_values.keys())

    for player in lineup_names:
        # Coincidencia exacta primero
        if player in squad_values:
            found.append(squad_values[player])
            continue
        # Fuzzy fallback
        close = difflib.get_close_matches(player, squad_names, n=1, cutoff=0.72)
        if close:
            found.append(squad_values[close[0]])

    if len(found) < 7:
        return None

    return round(sum(found), 1)


# ---------------------------------------------------------------------------
# CLI: python -m data.players <equipo>
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    team = " ".join(sys.argv[1:]) or "Argentina"
    print(f"Buscando valores de plantilla para: {team}")
    values = get_squad_values(team)
    if not values:
        print("  No se pudieron obtener datos.")
    else:
        total = sum(values.values())
        print(f"  Jugadores con valor: {len(values)}  |  Total: {total:.1f}M EUR")
        for name, val in sorted(values.items(), key=lambda x: -x[1])[:15]:
            print(f"    {name:<30} {val:6.1f}M")
