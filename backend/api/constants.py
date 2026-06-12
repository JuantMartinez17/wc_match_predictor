"""
backend/api/constants.py
========================
Constantes compartidas entre routers: IDs de equipos y códigos de banderas.

ID de equipo
------------
Entero positivo estable (1-48) asignado por orden alfabético ASCII del nombre
canónico en inglés. El orden es determinista mientras el conjunto de equipos no
cambie.

  "Algeria"                → 1
  "Argentina"              → 2
  "Korea Republic"         → 27
  "USA"                    → 47

Banderas
--------
Código ISO 3166-1 alpha-2 usado directamente por flagcdn.com
(ej. "ar" → flagcdn.com/w80/ar.png). England y Scotland usan las subdivisiones
de GB soportadas por flagcdn.
"""

from __future__ import annotations

import re
import unicodedata

from data.ingest import WC2026_TEAMS

# ---------------------------------------------------------------------------
# Generación de IDs numéricos
# ---------------------------------------------------------------------------


def _sort_key(canonical: str) -> str:
    """Clave ASCII normalizada para ordenamiento determinista."""
    s = (
        unicodedata.normalize("NFKD", canonical)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    s = re.sub(r"['\"]", "", s).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# Orden estable: alfabético por clave ASCII del nombre canónico
_SORTED_TEAMS: list[str] = sorted(WC2026_TEAMS, key=_sort_key)

# canonical (inglés) → id numérico (1-based)
TEAM_IDS: dict[str, int] = {
    canonical: i + 1 for i, canonical in enumerate(_SORTED_TEAMS)
}

# id numérico → canonical (inglés) — para resolver el request del frontend
CANONICAL_BY_ID: dict[int, str] = {v: k for k, v in TEAM_IDS.items()}


def team_id(canonical: str) -> int | None:
    """Devuelve el ID numérico del equipo dado su nombre canónico. None si no está en el torneo."""
    return TEAM_IDS.get(canonical)


def canonical_from_id(tid: int) -> str | None:
    """Devuelve el nombre canónico dado un ID numérico. None si no existe."""
    return CANONICAL_BY_ID.get(tid)


# ---------------------------------------------------------------------------
# Banderas (códigos ISO2 para flagcdn.com)
# ---------------------------------------------------------------------------

_FLAG_ISO2: dict[str, str] = {
    # CONMEBOL
    "Argentina": "ar",
    "Brazil": "br",
    "Colombia": "co",
    "Ecuador": "ec",
    "Paraguay": "py",
    "Uruguay": "uy",
    # UEFA
    "Austria": "at",
    "Belgium": "be",
    "Bosnia and Herzegovina": "ba",
    "Croatia": "hr",
    "Czechia": "cz",
    "England": "gb-eng",
    "France": "fr",
    "Germany": "de",
    "Netherlands": "nl",
    "Norway": "no",
    "Portugal": "pt",
    "Scotland": "gb-sct",
    "Spain": "es",
    "Sweden": "se",
    "Switzerland": "ch",
    "Turkey": "tr",
    # CAF
    "Algeria": "dz",
    "Cabo Verde": "cv",
    "Congo DR": "cd",
    "Côte d'Ivoire": "ci",
    "Egypt": "eg",
    "Ghana": "gh",
    "Morocco": "ma",
    "Senegal": "sn",
    "South Africa": "za",
    "Tunisia": "tn",
    # AFC
    "Australia": "au",
    "Iran": "ir",
    "Iraq": "iq",
    "Japan": "jp",
    "Jordan": "jo",
    "Korea Republic": "kr",
    "Qatar": "qa",
    "Saudi Arabia": "sa",
    "Uzbekistan": "uz",
    # CONCACAF
    "Canada": "ca",
    "Curaçao": "cw",
    "Haiti": "ht",
    "Mexico": "mx",
    "Panama": "pa",
    "USA": "us",
    # OFC
    "New Zealand": "nz",
}


def flag(team: str) -> str:
    """Devuelve el código ISO2 para usar con flagcdn.com. Fallback: 'un' (bandera de la ONU)."""
    return _FLAG_ISO2.get(team, "un")
