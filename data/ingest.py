"""
data/ingest.py
==============
Módulo de ingesta real. Descarga el historial completo de resultados de
selecciones desde el repositorio público martj42/international_results
(GitHub, CC BY 4.0) y normaliza los datos al esquema interno del proyecto.

Uso rápido:
    python -m data.ingest                  # descarga y reporta estadísticas
    python -m data.ingest --refresh        # fuerza re-descarga ignorando caché

La fuente se actualiza tras cada fecha FIFA. El caché local tiene un TTL de
24 horas para evitar requests redundantes en ejecuciones frecuentes.
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from data.loader import validate_matches

# ---------------------------------------------------------------------------
# Constantes de fuente y caché
# ---------------------------------------------------------------------------

_RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/"
    "international_results/master/results.csv"
)
_CACHE_TTL_SECONDS = 24 * 3600  # 24 horas


# ---------------------------------------------------------------------------
# Mapeo de torneos → categorías internas del proyecto
# ---------------------------------------------------------------------------

_TOURNAMENT_MAP: dict[str, str] = {
    # Mundial
    "FIFA World Cup": "world_cup",
    # Clasificatorias mundialistas
    "FIFA World Cup qualification": "qualifier",
    "FIFA World Cup qualification (CONMEBOL)": "qualifier",
    "FIFA World Cup qualification (CONCACAF)": "qualifier",
    "FIFA World Cup qualification (UEFA)": "qualifier",
    "FIFA World Cup qualification (CAF)": "qualifier",
    "FIFA World Cup qualification (AFC)": "qualifier",
    "FIFA World Cup qualification (OFC)": "qualifier",
    "FIFA World Cup qualification (AFC-CONMEBOL play-off)": "qualifier",
    "FIFA World Cup qualification (AFC-CONCACAF play-off)": "qualifier",
    "FIFA World Cup qualification (CONMEBOL-OFC play-off)": "qualifier",
    # Copas continentales
    "UEFA Euro": "continental_cup",
    "Copa América": "continental_cup",
    "Africa Cup of Nations": "continental_cup",
    "AFC Asian Cup": "continental_cup",
    "CONCACAF Gold Cup": "continental_cup",
    "OFC Nations Cup": "continental_cup",
    "COSAFA Cup": "continental_cup",
    "WAFU Cup of Nations": "continental_cup",
    # Clasificatorias continentales
    "UEFA Euro qualification": "qualifier",
    "Copa América qualification": "qualifier",
    "Africa Cup of Nations qualification": "qualifier",
    "AFC Asian Cup qualification": "qualifier",
    "CONCACAF Gold Cup qualification": "qualifier",
    "CONCACAF Championship": "qualifier",
    # Nations Leagues
    "UEFA Nations League": "nations_league",
    "UEFA Nations League A": "nations_league",
    "UEFA Nations League B": "nations_league",
    "UEFA Nations League C": "nations_league",
    "UEFA Nations League D": "nations_league",
    "CONCACAF Nations League": "nations_league",
    "CONCACAF Nations League A": "nations_league",
    "CONCACAF Nations League B": "nations_league",
    "CONCACAF Nations League C": "nations_league",
    "UEFA Nations League Finals": "nations_league",
    # Amistosos
    "Friendly": "friendly",
    "Friendlies": "friendly",
}


# ---------------------------------------------------------------------------
# Normalización de nombres de equipos (fuente → nombres del proyecto)
# ---------------------------------------------------------------------------

_TEAM_NAME_MAP: dict[str, str] = {
    # Asia
    "South Korea": "Korea Republic",
    "Republic of Korea": "Korea Republic",
    "IR Iran": "Iran",
    # Europa
    "United States": "USA",
    "Czech Republic": "Czechia",
    "Turkey": "Turkey",        # ya existe, solo por claridad
    "Türkiye": "Turkey",       # nombre oficial FIFA desde 2022
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    # Africa
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "DR Congo": "Congo DR",
    "Democratic Republic of the Congo": "Congo DR",
    "Cape Verde": "Cabo Verde",
    "Cape Verde Islands": "Cabo Verde",
    # Oceanía
    # Otros
    "Curacao": "Curaçao",
}


# ---------------------------------------------------------------------------
# Equipos del Mundial 2026 (los que nos interesan por defecto)
# ---------------------------------------------------------------------------

WC2026_TEAMS: frozenset[str] = frozenset({
    # CONMEBOL (6)
    "Argentina", "Brazil", "Colombia", "Ecuador", "Paraguay", "Uruguay",
    # UEFA (16)
    "Austria", "Belgium", "Bosnia and Herzegovina", "Croatia", "Czechia",
    "England", "France", "Germany", "Netherlands", "Norway",
    "Portugal", "Scotland", "Spain", "Sweden", "Switzerland", "Turkey",
    # CAF (10)
    "Algeria", "Cabo Verde", "Congo DR", "Côte d'Ivoire", "Egypt",
    "Ghana", "Morocco", "Senegal", "South Africa", "Tunisia",
    # AFC (9)
    "Australia", "Iran", "Iraq", "Japan", "Jordan",
    "Korea Republic", "Qatar", "Saudi Arabia", "Uzbekistan",
    # CONCACAF (6, incluye sedes)
    "Canada", "Curaçao", "Haiti", "Mexico", "Panama", "USA",
    # OFC (1)
    "New Zealand",
})


# ---------------------------------------------------------------------------
# Funciones internas de caché
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: Path) -> Path:
    url_hash = hashlib.md5(_RESULTS_URL.encode()).hexdigest()[:8]
    return cache_dir / f"international_results_{url_hash}.csv"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < _CACHE_TTL_SECONDS


def _age_label(path: Path) -> str:
    age_h = (time.time() - path.stat().st_mtime) / 3600
    return f"{age_h:.0f}h de antigüedad"


# Columnas que realmente usa build_dataset; el CSV fuente trae además city/country
# (~48k filas) que nunca se usan. Leer solo estas recorta el pico de memoria.
_USECOLS = [
    "date", "home_team", "away_team",
    "home_score", "away_score", "tournament", "neutral",
]


def _read_results_csv(path: Path) -> pd.DataFrame:
    """Lee el CSV de resultados solo con las columnas necesarias.

    Si el esquema no coincide (columna faltante), cae a una lectura completa.
    """
    try:
        return pd.read_csv(path, parse_dates=["date"], usecols=_USECOLS)
    except (ValueError, KeyError):
        return pd.read_csv(path, parse_dates=["date"])


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def download_results(
    cache_dir: str | Path = "data/cache",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Descarga (o lee del caché local) el historial completo de resultados.

    Parameters
    ----------
    cache_dir : directorio donde se guarda el CSV descargado.
    force_refresh : si True, ignora el caché y re-descarga.

    Returns
    -------
    pd.DataFrame crudo con las columnas originales de la fuente.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir)

    if not force_refresh and _is_fresh(cached):
        print(f"  [cache] Usando datos locales ({_age_label(cached)})")
        return _read_results_csv(cached)

    print("  [descarga] Conectando a GitHub... ", end="", flush=True)
    try:
        urllib.request.urlretrieve(_RESULTS_URL, cached)
        print("OK")
    except urllib.error.URLError as exc:
        if cached.exists():
            print(f"  [aviso] Sin red — usando caché ({_age_label(cached)})")
        else:
            raise RuntimeError(
                f"No se pudo descargar los datos y no existe caché local.\n"
                f"Error: {exc}\n"
                f"URL: {_RESULTS_URL}"
            ) from exc

    return _read_results_csv(cached)


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def _map_tournament(name: str) -> str:
    """Mapea el nombre del torneo a la categoría interna. Fallback heurístico."""
    if name in _TOURNAMENT_MAP:
        return _TOURNAMENT_MAP[name]
    low = name.lower()
    if "world cup" in low:
        return "qualifier" if "qualif" in low else "world_cup"
    if "qualif" in low or "eliminat" in low or "playoff" in low:
        return "qualifier"
    if "nations league" in low:
        return "nations_league"
    if "friendly" in low or "amistoso" in low:
        return "friendly"
    if any(t in low for t in ("euro", "copa", "africa cup", "asian cup", "gold cup")):
        return "continental_cup"
    return "friendly"  # fallback conservador


def _normalize_team(name: str) -> str:
    return _TEAM_NAME_MAP.get(name, name)


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def build_dataset(
    teams: frozenset[str] | set[str] | None = None,
    since_year: int = 2018,
    cache_dir: str | Path = "data/cache",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Construye el DataFrame de partidos real, normalizado y validado.

    Parameters
    ----------
    teams : conjunto de nombres de equipo a incluir.
             Si es None, usa WC2026_TEAMS (32 clasificados al Mundial 2026).
    since_year : incluye solo partidos desde este año (UTC).
    cache_dir : carpeta local de caché.
    force_refresh : si True, re-descarga aunque el caché sea fresco.

    Returns
    -------
    pd.DataFrame validado por ``data.loader.validate_matches``, listo para
    alimentar directamente a ``MatchPredictor``.
    """
    if teams is None:
        teams = WC2026_TEAMS

    raw = download_results(cache_dir=cache_dir, force_refresh=force_refresh)

    # Normalizar nombres de equipos
    raw["home_team"] = raw["home_team"].map(_normalize_team)
    raw["away_team"] = raw["away_team"].map(_normalize_team)

    # Filtrar: al menos uno de los equipos del torneo, y desde since_year
    mask = (
        (raw["home_team"].isin(teams) | raw["away_team"].isin(teams))
        & (raw["date"].dt.year >= since_year)
    )
    filtered = raw.loc[mask].copy()

    # Renombrar al esquema interno
    filtered = filtered.rename(columns={
        "home_score": "home_goals",
        "away_score": "away_goals",
        "tournament": "competition",
    })

    # Mapear torneos
    filtered["competition"] = filtered["competition"].map(_map_tournament)

    # Descartar filas con marcadores no numéricos (partidos cancelados, etc.)
    filtered["home_goals"] = pd.to_numeric(filtered["home_goals"], errors="coerce")
    filtered["away_goals"] = pd.to_numeric(filtered["away_goals"], errors="coerce")
    filtered = filtered.dropna(subset=["home_goals", "away_goals"]).copy()

    # Asegurar que neutral sea bool
    if "neutral" in filtered.columns:
        filtered["neutral"] = filtered["neutral"].astype(bool)
    else:
        filtered["neutral"] = False

    keep = ["date", "home_team", "away_team", "home_goals", "away_goals",
            "competition", "neutral"]
    filtered = filtered[keep]

    teams_in_data = set(filtered["home_team"]) | set(filtered["away_team"])
    print(
        f"  [dataset] {len(filtered)} partidos ({since_year}–presente) | "
        f"{len(teams_in_data)} equipos únicos"
    )

    missing = sorted(teams - teams_in_data)
    if missing:
        print(f"  [aviso] Equipos sin datos en la ventana: {missing}")

    return validate_matches(filtered)


# ---------------------------------------------------------------------------
# CLI mínima: python -m data.ingest [--refresh]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    force = "--refresh" in sys.argv
    print("=" * 60)
    print(" INGESTA DE DATOS REALES — Mundial 2026")
    print("=" * 60)

    df = build_dataset(since_year=2018, force_refresh=force)

    print(f"\nRango de fechas : {df['date'].min().date()} - {df['date'].max().date()}")
    print(f"Partidos totales: {len(df)}")
    print(f"Equipos únicos  : {df['home_team'].nunique() + df['away_team'].nunique()} "
          f"(home+away, con duplicados)")

    print("\nPartidos por categoría:")
    for comp, n in df["competition"].value_counts().items():
        print(f"  {comp:20s}: {n}")

    print("\nEquipos con más partidos (top 10):")
    all_teams = pd.concat([df["home_team"], df["away_team"]])
    for team, n in all_teams.value_counts().head(10).items():
        print(f"  {team:20s}: {n}")

    print("\n[OK] Dataset listo para usar en MatchPredictor.")
